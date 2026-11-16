from decimal import Decimal

from semantic_lab.evals.reference import sort_rows


def test_nulls_sort_last_in_a_key_column() -> None:
    rows: list[list[object]] = [["b", 1], [None, 2], ["a", 3]]
    sort_rows(rows, [0])
    assert rows == [["a", 3], ["b", 1], [None, 2]]


def test_values_of_different_types_in_a_key_column_do_not_raise() -> None:
    rows: list[list[object]] = [["x", 1], [Decimal("2.5"), 2], [None, 3], [7, 4]]
    sort_rows(rows, [0])
    seconds = [row[1] for row in rows]
    assert seconds[-1] == 3
    assert set(seconds) == {1, 2, 3, 4}


def test_rows_sort_by_each_key_column_in_turn() -> None:
    rows: list[list[object]] = [["b", None], ["a", 2], ["b", 1], ["a", None]]
    sort_rows(rows, [0, 1])
    assert rows == [["a", 2], ["a", None], ["b", 1], ["b", None]]
