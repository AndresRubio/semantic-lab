from datetime import date
from decimal import Decimal

import pytest

from semantic_lab.domain.records import (
    DATA_TABLES,
    Dataset,
    SalesOrder,
    column_types,
    columns,
    record_type,
    rows,
)


def test_the_data_tables_are_the_fourteen_pairs_in_creation_order() -> None:
    assert len(DATA_TABLES) == 14
    assert DATA_TABLES[0] == ("cooperative", "cooperatives")


def test_a_table_name_gives_its_record_type() -> None:
    assert record_type("sales_order") is SalesOrder


def test_a_name_that_is_no_data_table_is_a_key_error() -> None:
    with pytest.raises(KeyError):
        record_type("concept")


def test_a_table_name_gives_its_columns_in_field_order() -> None:
    assert columns("farm") == ("code", "name", "cooperative_code", "altitude_m")


def test_a_name_that_is_no_data_table_has_no_columns() -> None:
    with pytest.raises(KeyError):
        columns("concept")


def test_rows_returns_the_dataset_attribute(dataset: Dataset) -> None:
    assert rows(dataset, "lot") is dataset.lots


def test_a_table_name_gives_the_type_of_each_column_without_its_none() -> None:
    assert column_types("cooperative_certification") == {
        "cooperative_code": str,
        "certification": str,
        "valid_from": date,
        "valid_until": date,
    }


def test_every_column_of_every_data_table_holds_one_of_four_types() -> None:
    held = {kind for table, _ in DATA_TABLES for kind in column_types(table).values()}
    assert held == {str, int, Decimal, date}


def test_a_name_that_is_no_data_table_has_no_column_types() -> None:
    with pytest.raises(KeyError):
        column_types("concept")
