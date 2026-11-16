"""The seed command: load the taxonomies, generate the dataset and rebuild the Postgres tables."""

import argparse
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

import psycopg

from semantic_lab import config, redaction
from semantic_lab.domain.errors import GenerationError, TaxonomyError
from semantic_lab.rdf.taxonomy import load_taxonomy
from semantic_lab.seed import load
from semantic_lab.seed.generate import DEFAULT_SEED, generate


def main(argv: Sequence[str], env: Mapping[str, str], out: TextIO, err: TextIO) -> int:
    parser = argparse.ArgumentParser(
        prog="seed", description="Rebuild the Postgres tables from the taxonomies and a seed."
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="the generator seed")
    parser.add_argument(
        "--taxonomy-dir", type=Path, default=Path("ontology/taxonomy"), help="the .ttl files"
    )
    args = parser.parse_args(argv)
    try:
        settings = config.load(env)
    except config.MissingSetting as missing:
        err.write(f"missing setting: {missing.name}\n")
        return 2
    try:
        taxonomy = load_taxonomy(args.taxonomy_dir)
    except TaxonomyError as error:
        err.write(f"taxonomy: {error}\n")
        return 1
    try:
        dataset = generate(taxonomy, args.seed)
    except (GenerationError, TaxonomyError) as error:
        err.write(f"seed: {error}\n")
        return 1
    dsn = settings.postgres_dsn
    secrets = [redaction.dsn_password(dsn)]
    try:
        connection = psycopg.connect(dsn)
    except psycopg.ProgrammingError as error:
        # Only the connect step can fail on an unparsable DSN, and that message quotes it.
        err.write(f"postgres: {redaction.unparsable_detail(error, 'DSN')}\n")
        return 1
    except psycopg.Error as error:
        err.write(f"postgres: {redaction.detail(error, secrets)}\n")
        return 1
    try:
        with connection:
            counts = load.rebuild(connection, taxonomy, dataset)
    except psycopg.Error as error:
        err.write(f"postgres: {redaction.detail(error, secrets)}\n")
        return 1
    for table in load.TABLES:
        out.write(f"{table}  {counts[table]}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ, sys.stdout, sys.stderr))
