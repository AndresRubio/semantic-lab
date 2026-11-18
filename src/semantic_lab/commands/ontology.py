"""The ontology command: check the taxonomy, the ontology, the mapping and the exported data."""

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from rdflib import Graph

from semantic_lab.domain.errors import (
    GenerationError,
    MappingError,
    OntologyError,
    TaxonomyError,
)
from semantic_lab.domain.mapping import Mapping, problems
from semantic_lab.domain.ontology import NAMESPACE, Ontology
from semantic_lab.domain.sample import first_orders
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.rdf import export, shacl
from semantic_lab.rdf.mapping import load_mapping
from semantic_lab.rdf.ontology import ontology_graph, ontology_of
from semantic_lab.rdf.taxonomy import taxonomy_graph, taxonomy_of
from semantic_lab.seed.generate import DEFAULT_SEED, generate

SHOWN = 20


@dataclass(frozen=True)
class Check:
    name: str
    covered: str
    problems: tuple[str, ...]


def count(text: str) -> int:
    """An argparse type: a whole number, 0 or more."""
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError(f"must be 0 or more, got {value}")
    return value


def main(argv: Sequence[str], out: TextIO, err: TextIO) -> int:
    parser = argparse.ArgumentParser(
        prog="ontology",
        description="Check the taxonomy, the ontology, the mapping and the exported data.",
    )
    parser.add_argument(
        "--ontology-dir", type=Path, default=Path("ontology"), help="the folder of the files"
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="the generator seed")
    parser.add_argument("--orders", type=count, default=200, help="how many orders to export")
    parser.add_argument("--full", action="store_true", help="export every order")
    args = parser.parse_args(argv)
    try:
        checks = run_checks(args.ontology_dir, args.seed, None if args.full else args.orders)
    except (TaxonomyError, OntologyError, MappingError, GenerationError) as error:
        err.write(f"ontology: {' '.join(str(error).split())}\n")
        return 1
    for check in checks:
        status = "FAIL" if check.problems else "ok"
        out.write(f"{status:<6}{check.name:<17} {check.covered}\n")
        for line in check.problems[:SHOWN]:
            out.write(f"  {line}\n")
        if len(check.problems) > SHOWN:
            out.write(f"  and {len(check.problems) - SHOWN} more\n")
    return 1 if any(check.problems for check in checks) else 0


def run_checks(directory: Path, seed: int, orders: int | None) -> tuple[Check, ...]:
    """The four checks. `orders` is the number to export, or None for every order."""
    taxonomy_data = taxonomy_graph(directory / "taxonomy")
    ontology_data = ontology_graph(directory / "ontology.ttl")
    shapes = shacl.shapes_graph(directory / "shapes.ttl")

    taxonomy_found, taxonomy = shapes_then_loader(taxonomy_data, shapes, taxonomy_of, TaxonomyError)
    ontology_found, ontology = shapes_then_loader(ontology_data, shapes, ontology_of, OntologyError)
    mapping_found, mapping = mapping_check(directory / "mapping.yaml", taxonomy, ontology)

    data_found = Check("data shapes", "not run", ("the mapping check failed",))
    if taxonomy is not None and ontology is not None and mapping is not None:
        data_found = export_check(
            taxonomy, ontology, mapping, shapes, taxonomy_data, ontology_data, seed, orders
        )
    return (
        Check("taxonomy shapes", f"{len(taxonomy_data)} triples", taxonomy_found),
        Check("ontology shapes", f"{len(ontology_data)} triples", ontology_found),
        mapping_found,
        data_found,
    )


def mapping_check(
    file: Path, taxonomy: Taxonomy | None, ontology: Ontology | None
) -> tuple[Check, Mapping | None]:
    """The mapping check, and the mapping when it has no problem.

    The export trusts the mapping, so it only gets one that passed.
    """
    try:
        mapping = load_mapping(file)
    except MappingError as error:
        return Check("mapping", "not read", (str(error),)), None
    if taxonomy is None or ontology is None:
        absent = tuple(
            f"the {name} check failed"
            for name, value in (("taxonomy", taxonomy), ("ontology", ontology))
            if value is None
        )
        return Check("mapping", "not run", absent), None
    covered = (
        f"{len(mapping.classes)} classes, {len(mapping.properties)} properties, "
        f"{len(mapping.postgres_columns())} columns"
    )
    found = problems(mapping, ontology, taxonomy)
    return Check("mapping", covered, found), None if found else mapping


def export_check(
    taxonomy: Taxonomy,
    ontology: Ontology,
    mapping: Mapping,
    shapes: Graph,
    taxonomy_data: Graph,
    ontology_data: Graph,
    seed: int,
    orders: int | None,
) -> Check:
    """Export the sample as RDF and check it against the data shapes."""
    dataset = generate(taxonomy, seed)
    sample = dataset if orders is None else first_orders(dataset, orders)
    prefix = "" if orders is None else "the first "
    covered = f"{prefix}{len(sample.orders)} orders"
    found: tuple[str, ...]
    try:
        data = export.export(sample, taxonomy, ontology, mapping)
        for triple in taxonomy_data:
            data.add(triple)
        data_shapes = shacl.data_shapes(shapes, NAMESPACE)
        found = tuple(v.line() for v in shacl.validate(data, data_shapes, ontology_data))
        size = len(data)
    except MappingError as error:
        found, size = (f"export: {error}",), 0
    return Check("data shapes", f"{size} triples from {covered}", found)


def shapes_then_loader[T](
    graph: Graph, shapes: Graph, load: Callable[[Graph], T], refusal: type[Exception]
) -> tuple[tuple[str, ...], T | None]:
    """The problems of a graph and its value, which is None when the loader refuses.

    The problems are the shapes' violations. A refusal goes before them as one `loader:` line,
    so the cap on shown problems never cuts the reason the later checks did not run.
    """
    found = tuple(v.line() for v in shacl.validate(graph, shapes))
    try:
        return found, load(graph)
    except refusal as error:
        return (f"loader: {' '.join(str(error).split())}", *found), None


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], sys.stdout, sys.stderr))
