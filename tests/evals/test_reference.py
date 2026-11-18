from decimal import Decimal
from types import TracebackType
from typing import Any, NamedTuple

import pytest

from semantic_lab.evals.questions import Question, QuestionError
from semantic_lab.evals.reference import run_sql, sort_rows


class Column(NamedTuple):
    name: str


class FakeCursor:
    def __init__(self, names: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
        self.description = [Column(name) for name in names]
        self._rows = rows

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        return None

    def execute(self, sql: str) -> None:
        return None

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class FakeConnection:
    def __init__(self, names: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
        self._cursor = FakeCursor(names, rows)

    def cursor(self) -> FakeCursor:
        return self._cursor


def question(key: tuple[str, ...], ordered: bool = False) -> Question:
    return Question(
        id="metric-one",
        kind="metric",
        text="A test question.",
        columns=("country", "revenue"),
        key=key,
        ordered=ordered,
        sql="select 1",
    )


def rows_of(
    names: tuple[str, ...], rows: list[tuple[object, ...]], asked: Question
) -> list[list[object]]:
    connection: Any = FakeConnection(names, rows)
    return run_sql(connection, asked)


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


NAMES = ("country", "revenue")


def test_run_sql_sorts_an_unordered_question_by_its_key() -> None:
    rows = rows_of(NAMES, [("Peru", 3), ("Kenya", 5)], question(("country",)))
    assert rows == [["Kenya", 5], ["Peru", 3]]


def test_run_sql_keeps_the_order_of_an_ordered_question() -> None:
    rows = rows_of(NAMES, [("Peru", 3), ("Kenya", 5)], question(("country",), ordered=True))
    assert rows == [["Peru", 3], ["Kenya", 5]]


def test_run_sql_refuses_two_rows_with_the_same_key() -> None:
    with pytest.raises(QuestionError, match=r"metric-one.*key.*does not identify a row"):
        rows_of(NAMES, [("Peru", 3), ("Kenya", 5), ("Peru", 4)], question(("country",)))


def test_run_sql_refuses_a_repeated_key_in_an_ordered_question_too() -> None:
    with pytest.raises(QuestionError, match="does not identify a row"):
        rows_of(NAMES, [("Peru", 3), ("Peru", 3)], question(("country", "revenue"), ordered=True))


def test_run_sql_accepts_rows_that_differ_in_any_key_column() -> None:
    rows = rows_of(NAMES, [("Peru", 3), ("Peru", 4)], question(("country", "revenue")))
    assert rows == [["Peru", 3], ["Peru", 4]]


def test_run_sql_treats_two_nulls_in_the_key_as_the_same_value() -> None:
    with pytest.raises(QuestionError, match="does not identify a row"):
        rows_of(NAMES, [(None, 1), (None, 2)], question(("country",)))


def test_run_sql_refuses_other_columns() -> None:
    with pytest.raises(QuestionError, match="returns columns"):
        rows_of(("country", "other"), [], question(("country",)))
