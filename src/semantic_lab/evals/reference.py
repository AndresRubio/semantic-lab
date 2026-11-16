"""Runs a question's reference SQL and returns its rows in a fixed order."""

from typing import Any

import psycopg

from semantic_lab.evals.questions import Question, QuestionError


def sort_rows(rows: list[list[object]], positions: list[int]) -> None:
    """Sort rows in place by the columns at `positions`.

    A null sorts after every value, and values of different types are ordered by the name of
    their type first, so no comparison ever mixes types and a nullable key column cannot raise.
    """
    rows.sort(
        key=lambda row: tuple(
            (row[position] is None, type(row[position]).__name__, row[position])
            for position in positions
        )
    )


def run_sql(connection: psycopg.Connection[Any], question: Question) -> list[list[object]]:
    """The rows the reference SQL gives. They are sorted by the key columns unless the question
    is ordered, so that two runs of an unordered question compare equal."""
    with connection.cursor() as cursor:
        cursor.execute(question.sql)
        names = tuple(column.name for column in cursor.description or ())
        if names != question.columns:
            raise QuestionError(
                f"question {question.id}: the query returns columns {list(names)}, "
                f"the question declares {list(question.columns)}"
            )
        rows = [list(row) for row in cursor.fetchall()]
    if not question.ordered:
        positions = [question.columns.index(name) for name in question.key]
        sort_rows(rows, positions)
    return rows
