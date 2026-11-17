"""The questions command: check each stored answer against the seeded database, or rewrite them."""

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

import psycopg

from semantic_lab import config, pg, redaction
from semantic_lab.evals import questions, reference
from semantic_lab.evals.questions import MissingAnswer, Question, QuestionError

FILES = ("dev.toml", "heldout.toml")


def _render(rows: list[list[object]]) -> str:
    lines = ",\n".join(f"    {json.dumps(row, ensure_ascii=False)}" for row in rows)
    return f'{{\n  "rows": [\n{lines}\n  ]\n}}\n'


def _write_expected(directory: Path, question: Question, rows: list[list[object]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{question.id}.json").write_text(_render(rows), encoding="utf-8")


def _check(
    connection: psycopg.Connection[Any],
    question: Question,
    directory: Path,
    write: bool,
    dsn: str,
    out: TextIO,
) -> bool:
    """Run one question and print its line. A query that fails is this question's error and
    nothing else: the connection is rolled back so the next question starts clean."""
    try:
        rows = questions.to_json_rows(reference.run_sql(connection, question))
        if write:
            _write_expected(directory, question, rows)
            out.write(f"wrote {question.id}\n")
            return True
        try:
            expected = questions.read_expected(directory, question.id)
        except MissingAnswer:
            out.write(f"MISSING {question.id}\n")
            return False
    except QuestionError as error:
        connection.rollback()
        out.write(f"ERROR {question.id}  {error}\n")
        return False
    except psycopg.Error as error:
        connection.rollback()
        out.write(f"ERROR {question.id}  {pg.detail(error, dsn)}\n")
        return False
    connection.rollback()
    if rows == expected:
        out.write(f"ok {question.id}\n")
        return True
    out.write(f"DRIFT {question.id}\n")
    return False


def main(argv: Sequence[str], env: Mapping[str, str], out: TextIO, err: TextIO) -> int:
    parser = argparse.ArgumentParser(
        prog="questions",
        description="Check the stored answers of the evaluation questions against Postgres.",
    )
    parser.add_argument(
        "--questions-dir", type=Path, default=Path("questions"), help="dev.toml, heldout.toml, expected/"
    )
    parser.add_argument(
        "--write-expected",
        action="store_true",
        help="write each stored answer from the database instead of checking it",
    )
    args = parser.parse_args(argv)
    try:
        settings = config.load(env)
    except config.MissingSetting as missing:
        err.write(f"missing setting: {missing.name}\n")
        return 2
    try:
        every = tuple(q for name in FILES for q in questions.load(args.questions_dir / name))
        ids = [question.id for question in every]
        if len(ids) != len(set(ids)):
            raise QuestionError("a question id appears in both files")
    except QuestionError as error:
        err.write(f"questions: {error}\n")
        return 1
    dsn = settings.postgres_dsn
    expected_dir = args.questions_dir / "expected"
    try:
        connection = pg.connect(dsn)
    except pg.ConnectError as error:
        err.write(f"postgres: {error}\n")
        return 1
    try:
        with connection:
            # A reference query reads only. The server refuses a write in a read-only transaction.
            connection.read_only = True
            results = [
                _check(connection, question, expected_dir, args.write_expected, dsn, out)
                for question in every
            ]
    except psycopg.Error as error:
        # The connection itself failed in the middle of the run, not one question's query.
        err.write(f"postgres: {pg.detail(error, dsn)}\n")
        return 1
    except OSError as error:
        # Only writing a stored answer touches a file once the connection is open.
        err.write(f"questions: {redaction.detail(error)}\n")
        return 1
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], os.environ, sys.stdout, sys.stderr))
