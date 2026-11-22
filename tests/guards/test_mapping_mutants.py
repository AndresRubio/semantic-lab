"""Mechanical edits of the repository's mapping: a check must refuse each one.

A refusal is the reader's MappingError, a problem line of the mapping check, the export's
MappingError or a violation of the data shapes, which is how the ontology command reports each.
Any other exception fails the test, and so does a log line.
"""

from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from rdflib import Graph

from semantic_lab.domain.errors import MappingError
from semantic_lab.domain.mapping import Mapping, problems
from semantic_lab.domain.ontology import NAMESPACE, Ontology
from semantic_lab.domain.records import Dataset
from semantic_lab.domain.sample import first_orders
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.rdf import shacl
from semantic_lab.rdf.export import export
from semantic_lab.rdf.mapping import load_mapping
from semantic_lab.rdf.ontology import ontology_graph
from semantic_lab.rdf.taxonomy import taxonomy_graph
from tests.support import data_faults
from tests.support.paths import MAPPING_FILE, ONTOLOGY_FILE, TAXONOMY_DIRECTORY

MAPPING = load_mapping(MAPPING_FILE)
TERMS = [entry.iri.removeprefix(NAMESPACE) for entry in MAPPING.properties]
LINES = MAPPING_FILE.read_text(encoding="utf-8").splitlines()
EDITED = [n for n, line in enumerate(LINES) if line.strip() and not line.lstrip().startswith("#")]

# Pairs of properties whose Postgres targets can be exchanged with no check noticing. Each pair
# holds the same type on the same table, and no shape relates the two. A pair leaves this set
# when a rule that tells its two properties apart is added.
UNNOTICED = {
    frozenset({"city", "country"}),
    frozenset({"destinationPort", "originPort"}),
    frozenset({"pricePerKg", "weightKg"}),
}


@dataclass(frozen=True)
class World:
    taxonomy: Taxonomy
    ontology: Ontology
    taxonomy_rdf: Graph
    ontology_rdf: Graph
    shapes: Graph
    samples: tuple[Dataset, ...]  # a few orders first, then the 200 the command exports


@pytest.fixture(scope="module")
def world(taxonomy: Taxonomy, ontology: Ontology, shapes: Graph, dataset: Dataset) -> World:
    return World(
        taxonomy,
        ontology,
        taxonomy_graph(TAXONOMY_DIRECTORY),
        ontology_graph(ONTOLOGY_FILE),
        shacl.data_shapes(shapes, NAMESPACE),
        (data_faults.fault_sample(dataset), first_orders(dataset, 200)),
    )


def refused_by(mapping: Mapping, world: World) -> str | None:
    """The first check that refuses the mapping, in the command's order, or None."""
    if problems(mapping, world.ontology, world.taxonomy):
        return "the mapping check"
    for sample in world.samples:
        try:
            data = export(sample, world.taxonomy, world.ontology, mapping)
        except MappingError:
            return "the export"
        data += world.taxonomy_rdf
        if shacl.validate(data, world.shapes, world.ontology_rdf):
            return "the data shapes"
    return None


def swapped(mapping: Mapping, one: str, other: str) -> Mapping:
    """The mapping with the Postgres targets of two properties exchanged."""
    entries = {entry.iri.removeprefix(NAMESPACE): entry for entry in mapping.properties}
    first, second = entries[one], entries[other]
    entries[one] = replace(first, columns=second.columns, link=second.link)
    entries[other] = replace(second, columns=first.columns, link=first.link)
    return replace(mapping, properties=tuple(entries.values()))


@pytest.mark.parametrize("term", TERMS[:-1])
def test_a_property_swapped_with_a_later_one_is_refused(
    term: str, world: World, caplog: pytest.LogCaptureFixture
) -> None:
    for other in TERMS[TERMS.index(term) + 1 :]:
        refused = refused_by(swapped(MAPPING, term, other), world)
        known = frozenset({term, other}) in UNNOTICED
        assert (refused is None) == known, f"{term} with {other}: refused by {refused}"
    assert caplog.records == []


def test_every_unnoticed_pair_names_two_mapped_properties() -> None:
    assert all(len(pair) == 2 and pair <= set(TERMS) for pair in UNNOTICED)


def refused_as_text(lines: list[str], file: Path, world: World) -> bool:
    file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        mapping = load_mapping(file)
    except MappingError:
        return True
    return refused_by(mapping, world) is not None


def test_the_mapping_without_any_one_of_its_lines_is_refused(
    tmp_path: Path, world: World, caplog: pytest.LogCaptureFixture
) -> None:
    for n in EDITED:
        without = LINES[:n] + LINES[n + 1 :]
        assert refused_as_text(without, tmp_path / "mapping.yaml", world), f"line {n + 1}"
    assert caplog.records == []


def test_the_mapping_with_any_one_of_its_lines_twice_is_refused(
    tmp_path: Path, world: World, caplog: pytest.LogCaptureFixture
) -> None:
    for n in EDITED:
        twice = [*LINES[: n + 1], *LINES[n:]]
        assert refused_as_text(twice, tmp_path / "mapping.yaml", world), f"line {n + 1}"
    assert caplog.records == []
