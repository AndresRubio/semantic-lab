import dataclasses

import pytest

from semantic_lab.domain.records import Dataset
from semantic_lab.domain.sample import first_orders


def test_it_keeps_the_first_orders_and_what_hangs_from_them(dataset: Dataset) -> None:
    sample = first_orders(dataset, 20)
    assert sample.orders == dataset.orders[:20]
    codes = {order.code for order in sample.orders}
    assert sample.order_lines
    assert all(line.order_code in codes for line in sample.order_lines)
    assert len(sample.order_lines) < len(dataset.order_lines)


def test_it_keeps_the_batches_the_lines_name_and_their_components(dataset: Dataset) -> None:
    sample = first_orders(dataset, 20)
    named = {line.roast_batch_code for line in sample.order_lines}
    assert {batch.code for batch in sample.roast_batches} == named
    assert sample.roast_batch_lots
    assert all(row.roast_batch_code in named for row in sample.roast_batch_lots)
    assert {row.roast_batch_code for row in sample.roast_batch_lots} <= named


def test_it_keeps_the_batch_components_of_every_kept_batch(dataset: Dataset) -> None:
    sample = first_orders(dataset, 20)
    kept = {batch.code for batch in sample.roast_batches}
    expected = tuple(r for r in dataset.roast_batch_lots if r.roast_batch_code in kept)
    assert sample.roast_batch_lots == expected


def test_the_other_tables_stay_whole(dataset: Dataset) -> None:
    sample = first_orders(dataset, 20)
    for name in ("lots", "customers", "products", "farms", "lot_farms", "quality_incidents"):
        assert getattr(sample, name) is getattr(dataset, name)


def test_a_negative_count_is_refused(dataset: Dataset) -> None:
    with pytest.raises(ValueError):
        first_orders(dataset, -1)


def test_a_count_at_or_above_the_orders_gives_the_same_dataset(dataset: Dataset) -> None:
    assert first_orders(dataset, len(dataset.orders)) == dataset
    assert first_orders(dataset, len(dataset.orders) + 5) == dataset


def test_a_count_of_zero_keeps_no_order(dataset: Dataset) -> None:
    sample = first_orders(dataset, 0)
    assert sample.orders == ()
    assert sample.order_lines == ()
    assert sample.roast_batches == ()
    assert sample.roast_batch_lots == ()
    assert dataclasses.replace(sample, orders=()) == sample
