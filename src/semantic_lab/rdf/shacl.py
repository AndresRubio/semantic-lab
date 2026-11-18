from dataclasses import dataclass
from pathlib import Path

import pyshacl
from pyshacl.errors import ReportableRuntimeError
from rdflib import Graph, URIRef
from rdflib.namespace import SH

from semantic_lab.domain.errors import OntologyError
from semantic_lab.rdf import turtle


@dataclass(frozen=True)
class Violation:
    focus: str
    constraint: str  # local name of the constraint component, such as "MinCountConstraintComponent"
    path: str | None  # None when the path is not a single IRI
    value: str | None
    message: str

    def line(self) -> str:
        where = f" {self.path}" if self.path else ""
        return f"{self.focus} {self.constraint}{where}: {self.message}"


def shapes_graph(file: Path) -> Graph:
    """Read the shapes file into a graph."""
    return turtle.read([file], OntologyError)


def validate(data: Graph, shapes: Graph, ontology: Graph | None = None) -> tuple[Violation, ...]:
    """Check `data` against `shapes`, sorted by focus, constraint, path and message.

    With `ontology`, a shape that targets a class also targets its subclasses. No other
    inference runs.
    """
    try:
        _, report, _ = pyshacl.validate(
            data, shacl_graph=shapes, ont_graph=ontology, inference="none"
        )
    except ReportableRuntimeError as cause:
        reason = " ".join(str(cause).split()) or type(cause).__name__
        raise OntologyError(f"shapes: {reason}") from cause
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
                value=None if value is None else str(value),
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
