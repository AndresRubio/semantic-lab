import dataclasses
import time
from decimal import Decimal
from typing import Any

import psycopg
import pytest

from semantic_lab.config import Settings
from semantic_lab.domain.records import Dataset
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import load

pytestmark = pytest.mark.db


def _counts(connection: psycopg.Connection[Any]) -> dict[str, int]:
    counts = {}
    for table in load.TABLES:
        row = connection.execute(f"select count(*) from {table}").fetchone()
        assert row is not None
        counts[table] = row[0]
    return counts


def _total(connection: psycopg.Connection[Any]) -> Decimal:
    row = connection.execute("select sum(amount) from order_line").fetchone()
    assert row is not None
    return row[0]


def test_every_table_holds_its_rows(
    seeded: Settings, taxonomy: Taxonomy, dataset: Dataset
) -> None:
    with psycopg.connect(seeded.postgres_dsn) as connection:
        counts = _counts(connection)
    for table, attribute in load.DATA_TABLES:
        assert counts[table] == len(getattr(dataset, attribute)), table
    assert counts["concept"] == 70
    assert counts["concept_closure"] == len(taxonomy.closure())


def test_money_and_dates_survive_the_round_trip(seeded: Settings, dataset: Dataset) -> None:
    line = dataset.order_lines[0]
    lot = dataset.lots[0]
    with psycopg.connect(seeded.postgres_dsn) as connection:
        line_row = connection.execute(
            "select unit_price, amount, kg from order_line where order_code = %s and line_no = %s",
            (line.order_code, line.line_no),
        ).fetchone()
        lot_row = connection.execute(
            "select harvested_on, weight_kg, price_per_kg from lot where code = %s",
            (lot.code,),
        ).fetchone()
    assert line_row is not None
    assert line_row == (line.unit_price, line.amount, line.kg)
    assert all(isinstance(value, Decimal) for value in line_row)
    assert lot_row == (lot.harvested_on, lot.weight_kg, lot.price_per_kg)


def test_a_second_rebuild_leaves_the_same_rows(
    seeded: Settings, taxonomy: Taxonomy, dataset: Dataset
) -> None:
    with psycopg.connect(seeded.postgres_dsn) as connection:
        before = _counts(connection)
        total = connection.execute("select sum(amount) from order_line").fetchone()
    with psycopg.connect(seeded.postgres_dsn) as connection:
        counts = load.rebuild(connection, taxonomy, dataset)
    with psycopg.connect(seeded.postgres_dsn) as connection:
        after = _counts(connection)
        total_after = connection.execute("select sum(amount) from order_line").fetchone()
    assert after == before == counts
    assert total_after == total


def test_a_failed_rebuild_keeps_the_old_rows(
    seeded: Settings, taxonomy: Taxonomy, dataset: Dataset
) -> None:
    broken_line = dataclasses.replace(dataset.order_lines[0], roast_batch_code="B-9999")
    broken = dataclasses.replace(dataset, order_lines=(broken_line, *dataset.order_lines[1:]))
    with psycopg.connect(seeded.postgres_dsn) as connection:
        before = _counts(connection)
        total = _total(connection)
    with psycopg.connect(seeded.postgres_dsn) as connection:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            load.rebuild(connection, taxonomy, broken)
    with psycopg.connect(seeded.postgres_dsn) as connection:
        assert _counts(connection) == before
        assert _total(connection) == total


def test_a_view_over_a_table_makes_the_rebuild_fail_and_keeps_the_rows(
    seeded: Settings, taxonomy: Taxonomy, dataset: Dataset
) -> None:
    with psycopg.connect(seeded.postgres_dsn, autocommit=True) as connection:
        before = _counts(connection)
        total = _total(connection)
        connection.execute("create view order_line_copy as select * from order_line")
    try:
        with psycopg.connect(seeded.postgres_dsn) as connection:
            with pytest.raises(psycopg.Error):
                load.rebuild(connection, taxonomy, dataset)
        with psycopg.connect(seeded.postgres_dsn) as connection:
            assert _counts(connection) == before
            assert _total(connection) == total
            view = connection.execute("select to_regclass('order_line_copy')").fetchone()
            assert view is not None
            assert view[0] is not None
    finally:
        with psycopg.connect(seeded.postgres_dsn, autocommit=True) as connection:
            connection.execute("drop view if exists order_line_copy")


def test_a_lock_held_by_another_session_makes_the_rebuild_fail_in_seconds(
    seeded: Settings, taxonomy: Taxonomy, dataset: Dataset
) -> None:
    with psycopg.connect(seeded.postgres_dsn) as connection:
        before = _counts(connection)
        total = _total(connection)
    with psycopg.connect(seeded.postgres_dsn) as holder:
        holder.execute("lock table order_line in access share mode")
        started = time.monotonic()
        with psycopg.connect(seeded.postgres_dsn) as connection:
            with pytest.raises(psycopg.Error):
                load.rebuild(connection, taxonomy, dataset)
        assert time.monotonic() - started < 10
    with psycopg.connect(seeded.postgres_dsn) as connection:
        assert _counts(connection) == before
        assert _total(connection) == total


def test_fruity_revenue_can_be_read_through_the_closure(seeded: Settings) -> None:
    query = """
        select p.code, sum(l.amount)
        from order_line l
        join product p on p.code = l.product_code
        join product_flavour f on f.product_code = p.code
        join concept_closure c on c.descendant_key = f.flavour_key
        where c.ancestor_key = 'flavour.fruity'
        group by p.code
    """
    with psycopg.connect(seeded.postgres_dsn) as connection:
        rows = connection.execute(query).fetchall()
    assert rows
