"""The ontology command: check the taxonomy, the ontology, the mapping and the exported data."""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from semantic_lab.domain.errors import (
    GenerationError,
    MappingError,
    OntologyError,
    TaxonomyError,
)
from semantic_lab.domain.mapping import problems
from semantic_lab.domain.sample import first_orders
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


def main(argv: Sequence[str], out: TextIO, err: TextIO) -> int:
    parser = argparse.ArgumentParser(
        prog="ontology",
        description="Check the taxonomy, the ontology, the mapping and the exported data.",
    )
    parser.add_argument(
        "--ontology-dir", type=Path, default=Path("ontology"), help="the folder of the files"
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="the generator seed")
    parser.add_argument("--orders", type=int, default=200, help="how many orders to export")
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
    taxonomy = taxonomy_of(taxonomy_data)
    ontology_data = ontology_graph(directory / "ontology.ttl")
    ontology = ontology_of(ontology_data)
    shapes = shacl.shapes_graph(directory / "shapes.ttl")
    mapping = load_mapping(directory / "mapping.yaml")

    taxonomy_found = shacl.validate(taxonomy_data, shapes, ontology_data)
    ontology_found = shacl.validate(ontology_data, shapes)
    mapping_found = problems(mapping, ontology, taxonomy)

    dataset = generate(taxonomy, seed)
    sample = dataset if orders is None else first_orders(dataset, orders)
    covered = (
        f"{len(sample.orders)} orders" if orders is None else f"the first {orders} orders"
    )
    data_found: tuple[str, ...]
    try:
        data = export.export(sample, taxonomy, ontology, mapping)
        for triple in taxonomy_data:
            data.add(triple)
        data_found = tuple(v.line() for v in shacl.validate(data, shapes, ontology_data))
        data_size = len(data)
    except MappingError as error:
        data_found, data_size = (f"export: {error}",), 0
    return (
        Check(
            "taxonomy shapes",
            f"{len(taxonomy_data)} triples",
            tuple(v.line() for v in taxonomy_found),
        ),
        Check(
            "ontology shapes",
            f"{len(ontology_data)} triples",
            tuple(v.line() for v in ontology_found),
        ),
        Check(
            "mapping",
            f"{len(mapping.classes)} classes, {len(mapping.properties)} properties, "
            f"{len(mapping.postgres_columns())} columns",
            mapping_found,
        ),
        Check("data shapes", f"{data_size} triples from {covered}", data_found),
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], sys.stdout, sys.stderr))
