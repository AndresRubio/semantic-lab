"""Mutation check for the data shapes: take one rule out at a time and see a check notice.

    uv run python -m tests.support.mutate_shapes

It exits 0 when every rule is caught, 1 when one survives, and 2 when the shapes as they are
already fail a check, which would prove nothing. Any other error ends the run with its
traceback. It takes about twelve minutes on ten cores, so it is a tool to run after a change to
the data shapes and no part of the suite.
"""

import multiprocessing
import sys
from collections.abc import Callable, Mapping
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass

from rdflib import BNode, Graph, URIRef
from rdflib.namespace import SH
from rdflib.term import Node

from semantic_lab.domain.ontology import NAMESPACE
from semantic_lab.rdf import shacl
from semantic_lab.rdf.mapping import load_mapping
from semantic_lab.rdf.ontology import ontology_graph, ontology_of
from semantic_lab.rdf.taxonomy import load_taxonomy
from semantic_lab.seed import generate
from tests.support import data_faults
from tests.support.paths import MAPPING_FILE, ONTOLOGY_FILE, SHAPES_FILE, TAXONOMY_DIRECTORY

Rule = tuple[Node, Node, Node]

# The SHACL terms that state a rule. A triple with another predicate (a path, a message, a
# target) is part of how a rule is written, and removing it tests nothing by itself.
CONSTRAINTS = frozenset(
    SH[name]
    for name in (
        "and", "class", "closed", "datatype", "disjoint", "equals", "hasValue", "in",
        "languageIn", "lessThan", "lessThanOrEquals", "maxCount", "maxExclusive", "maxInclusive",
        "maxLength", "minCount", "minExclusive", "minInclusive", "minLength", "node", "nodeKind",
        "not", "or", "pattern", "property", "qualifiedValueShape", "sparql", "uniqueLang", "xone",
    )
)


@dataclass(frozen=True)
class World:
    """What the checks need: the data shapes, the sample they run on and the ontology graph."""

    shapes: Graph
    sample: Graph
    ontology: Graph


Check = Callable[[Graph, World], None]


def _conforms(shapes: Graph, world: World) -> None:
    assert not data_faults.violations(world.sample, shapes, world.ontology)


def _exact(change: data_faults.Change) -> Check:
    return lambda shapes, world: data_faults.check_exact(
        change, world.sample, shapes, world.ontology
    )


def _contained(change: data_faults.Change) -> Check:
    return lambda shapes, world: data_faults.check_contained(
        change, world.sample, shapes, world.ontology
    )


# The sample conforming, then every fault of tests/support/data_faults.py by its name. These are
# the parametrized tests of tests/guards/test_shapes.py. Its other tests take no part.
CHECKS: dict[str, Check] = {
    "the sample conforms": _conforms,
    **{name: _exact(change) for name, change in data_faults.CHANGES.items()},
    **{name: _contained(change) for name, change in data_faults.KINDS.items()},
}


def load() -> World:
    """The world of the repository's own files and the default seed."""
    taxonomy = load_taxonomy(TAXONOMY_DIRECTORY)
    ontology = ontology_graph(ONTOLOGY_FILE)
    sample = data_faults.data_graph(
        data_faults.fault_sample(generate.generate(taxonomy, generate.DEFAULT_SEED)),
        taxonomy,
        ontology_of(ontology),
        load_mapping(MAPPING_FILE),
    )
    return World(shacl.data_shapes(shacl.shapes_graph(SHAPES_FILE), NAMESPACE), sample, ontology)


def constraints(shapes: Graph) -> list[Rule]:
    """Every triple of the shapes that states a rule, in a stable order."""
    found = {(s, p, o) for s, p, o in shapes if p in CONSTRAINTS}
    return sorted(found, key=lambda rule: tuple(map(str, rule)))


def without(shapes: Graph, rule: Rule) -> Graph:
    """A copy of the shapes that lacks one triple.

    Without its `sh:closed` a shape also loses its `sh:ignoredProperties`: pyshacl refuses the
    shapes if they stay, and a refusal would say nothing about the checks.
    """
    mutant = data_faults.copy(shapes)
    mutant.remove(rule)
    if rule[1] == SH.closed:
        mutant.remove((rule[0], SH.ignoredProperties, None))
    return mutant


def caught_by(shapes: Graph, world: World, checks: Mapping[str, Check] = CHECKS) -> str | None:
    """The name of the first check that fails on these shapes, or None when all of them pass."""
    for name, check in checks.items():
        try:
            check(shapes, world)
        except AssertionError:
            return name
    return None


def describe(shapes: Graph, rule: Rule) -> str:
    """One line for a rule: the named shape that holds it, its path if it has one, and the rule."""
    subject, predicate, value = rule
    owner: Node | None = subject
    while owner is not None and not isinstance(owner, URIRef):
        owner = next(shapes.subjects(None, owner), None)
    path = shapes.value(subject, SH.path)
    parts = [_local(owner) if owner is not None else "?"]
    if isinstance(path, URIRef):
        parts.append(_local(path))
    parts.append(_local(predicate))
    if not isinstance(value, BNode):
        parts.append(_local(value))
    return " ".join(parts)


def _local(node: Node) -> str:
    return str(node).rsplit("#", 1)[-1]


# The parent loads the world once and forks, so every worker sees the same blank node names.
_WORLD: World | None = None


def _try(index: int) -> tuple[int, str | None]:
    assert _WORLD is not None
    rule = constraints(_WORLD.shapes)[index]
    return index, caught_by(without(_WORLD.shapes, rule), _WORLD)


def main() -> int:
    global _WORLD
    _WORLD = world = load()
    failing = caught_by(world.shapes, world)
    if failing is not None:
        print(f"the shapes as they are fail the check {failing!r}, so a mutant proves nothing")
        return 2
    rules = constraints(world.shapes)
    print(f"{len(rules)} rules")
    with ProcessPoolExecutor(mp_context=multiprocessing.get_context("fork")) as pool:
        caught = dict(pool.map(_try, range(len(rules))))
    survivors = [rule for index, rule in enumerate(rules) if caught[index] is None]
    for rule in survivors:
        print(f"survived: {describe(world.shapes, rule)}")
    print(f"{len(rules) - len(survivors)} caught, {len(survivors)} survived")
    return 1 if survivors else 0


if __name__ == "__main__":
    sys.exit(main())
