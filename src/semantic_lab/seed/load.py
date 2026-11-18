"""The Postgres schema of the seed and the loader that rebuilds it in one transaction."""

from collections.abc import Iterable, Sequence
from importlib.resources import files
from typing import Any

import psycopg

from semantic_lab.domain.records import DATA_TABLES, Dataset, columns, rows
from semantic_lab.domain.taxonomy import Taxonomy

CONCEPT_TABLES = ("concept", "concept_alt_label", "concept_closure")

# How long the rebuild waits for a lock on one of its tables before it gives up.
LOCK_TIMEOUT = "5s"

TABLES: tuple[str, ...] = CONCEPT_TABLES + tuple(table for table, _ in DATA_TABLES)


def _schema() -> str:
    return files("semantic_lab.seed").joinpath("schema.sql").read_text(encoding="utf-8")


def _copy(
    cursor: psycopg.Cursor[Any],
    table: str,
    columns: tuple[str, ...],
    rows: Iterable[Sequence[object]],
) -> int:
    count = 0
    with cursor.copy(f"copy {table} ({', '.join(columns)}) from stdin") as copy:
        for row in rows:
            copy.write_row(row)
            count += 1
    return count


def rebuild(
    connection: psycopg.Connection[Any], taxonomy: Taxonomy, dataset: Dataset
) -> dict[str, int]:
    """Drop and recreate the 17 tables and fill them, all in one transaction.

    A failure part way rolls everything back, so the previous rows stay. A session that holds a
    lock on one of the tables makes the rebuild fail after `LOCK_TIMEOUT` instead of waiting,
    and a view or foreign key outside the 17 tables makes the drop fail instead of vanishing. On
    a connection that already has a transaction open, the rebuild runs as a savepoint of that
    transaction.
    """
    counts: dict[str, int] = {}
    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(f"set local lock_timeout = '{LOCK_TIMEOUT}'")
        cursor.execute(_schema())
        counts["concept"] = _copy(
            cursor,
            "concept",
            ("key", "scheme", "iri", "label_en", "label_es", "parent_key"),
            (
                (c.key, c.scheme, c.iri, c.label_en, c.label_es, c.parent_key)
                for c in taxonomy.concepts
            ),
        )
        counts["concept_alt_label"] = _copy(
            cursor,
            "concept_alt_label",
            ("concept_key", "lang", "label"),
            (
                (c.key, lang, label)
                for c in taxonomy.concepts
                for lang, label in c.alt_labels
            ),
        )
        counts["concept_closure"] = _copy(
            cursor,
            "concept_closure",
            ("ancestor_key", "descendant_key", "depth"),
            taxonomy.closure(),
        )
        for table, _ in DATA_TABLES:
            names = columns(table)
            counts[table] = _copy(
                cursor,
                table,
                names,
                (tuple(getattr(record, name) for name in names) for record in rows(dataset, table)),
            )
    return counts
