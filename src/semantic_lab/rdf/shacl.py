from dataclasses import dataclass
from pathlib import Path

import pyshacl
from pyshacl.errors import ReportableRuntimeError
from rdflib import BNode, Graph, URIRef
from rdflib.namespace import SH
from rdflib.term import Node

from semantic_lab.domain.errors import OntologyError
from semantic_lab.rdf import turtle


@dataclass(frozen=True)
class Violation:
    focus: str
    constraint: str  # local name of the constraint component, such as "MinCountConstraintComponent"
    path: str | None  # None when the path is not a single IRI
    value: str | None  # None when there is no value or it is a blank node
    message: str

    def line(self) -> str:
        """One line. The value comes last unless the line already holds it: it is the focus, or
        the message quotes it, as pyshacl's own messages do."""
        where = f" {self.path}" if self.path else ""
        value = self.value
        held = (
            value is None
            or value == self.focus
            or f'"{value}"' in self.message
            or f"<{value}>" in self.message
        )
        ending = "" if held else f" (value {value})"
        return f"{self.focus} {self.constraint}{where}: {self.message}{ending}"


def shapes_graph(file: Path) -> Graph:
    """Read the shapes file into a graph."""
    return turtle.read([file], OntologyError)


def data_shapes(shapes: Graph, namespace: str) -> Graph:
    """The node shapes whose `sh:targetClass` is in `namespace`, with every node they reach.

    The prefix declarations come along, since a SPARQL rule reaches them through `sh:prefixes`.
    """
    todo: list[Node] = [
        shape for shape, target in shapes.subject_objects(SH.targetClass)
        if str(target).startswith(namespace)
    ]
    keep: set[Node] = set()
    while todo:
        node = todo.pop()
        if node not in keep:
            keep.add(node)
            todo.extend(o for o in shapes.objects(node, None) if isinstance(o, URIRef | BNode))
    group = Graph()
    for node in keep:
        for predicate, value in shapes.predicate_objects(node):
            group.add((node, predicate, value))
    return group


def validate(data: Graph, shapes: Graph, ontology: Graph | None = None) -> tuple[Violation, ...]:
    """Check `data` against `shapes`, sorted by focus, constraint, path and message.

    With `ontology`, a shape that targets a class also targets its subclasses. No other
    inference runs. A malformed shape raises `OntologyError` starting `shapes:`, and any other
    error that rdflib or pyshacl raises starts `validation:`.
    """
    try:
        _, report, _ = pyshacl.validate(
            data, shacl_graph=shapes, ont_graph=ontology, inference="none"
        )
    except ReportableRuntimeError as cause:
        reason = " ".join(str(cause).split()) or type(cause).__name__
        raise OntologyError(f"shapes: {reason}") from cause
    except Exception as cause:
        # The engine runs SPARQL from a file a person edits, and a fault there can raise any type.
        reason = " ".join(str(cause).split())
        raise OntologyError(f"validation: {type(cause).__name__}: {reason}") from cause
    return tuple(sorted(_violations(report), key=_order))


def _violations(report: Graph) -> list[Violation]:
    found = []
    for result in report.subjects(SH.resultSeverity, None):
        component = report.value(result, SH.sourceConstraintComponent)
        path = report.value(result, SH.resultPath)
        value = report.value(result, SH.value)
        messages = sorted(str(m) for m in report.objects(result, SH.resultMessage))
        found.append(
            Violation(
                focus=str(report.value(result, SH.focusNode)),
                constraint=str(component).rsplit("#", 1)[-1],
                path=str(path) if isinstance(path, URIRef) else None,
                value=None if value is None or isinstance(value, BNode) else str(value),
                message=" ".join(" ".join(messages).split()),
            )
        )
    return found


def _order(violation: Violation) -> tuple[str, str, str, str, str]:
    return (
        violation.focus,
        violation.constraint,
        violation.path or "",
        violation.message,
        violation.value or "",
    )
