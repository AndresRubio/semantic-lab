import pytest

from semantic_lab.domain.records import DATA_TABLES, Dataset, SalesOrder, record_type, rows


def test_the_data_tables_are_the_fourteen_pairs_in_creation_order() -> None:
    assert len(DATA_TABLES) == 14
    assert DATA_TABLES[0] == ("cooperative", "cooperatives")


def test_a_table_name_gives_its_record_type() -> None:
    assert record_type("sales_order") is SalesOrder


def test_a_name_that_is_no_data_table_is_a_key_error() -> None:
    with pytest.raises(KeyError):
        record_type("concept")


def test_rows_returns_the_dataset_attribute(dataset: Dataset) -> None:
    assert rows(dataset, "lot") is dataset.lots
