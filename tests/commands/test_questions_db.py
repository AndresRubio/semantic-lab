import io
import json
import shutil
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
import pytest

from semantic_lab.commands import questions
from semantic_lab.config import Settings
from tests.support import envfile

ROOT = Path(__file__).resolve().parent.parent.parent
STACK_ENV = ROOT / "tests" / "stack.env"
QUESTIONS = ROOT / "questions"
FRUITY = "hierarchy-kg-fruity-2025"
ORGANIC = "metric-organic-lots-2025"

pytestmark = pytest.mark.db


def run(*argv: str) -> tuple[int, list[str], str]:
    out, err = io.StringIO(), io.StringIO()
    code = questions.main(list(argv), envfile.read(STACK_ENV), out, err)
    return code, out.getvalue().splitlines(), err.getvalue()


def copy_of_questions(tmp_path: Path) -> Path:
    target = tmp_path / "questions"
    shutil.copytree(QUESTIONS, target)
    return target


def one_question(question_id: str, sql: str) -> str:
    return (
        "[[question]]\n"
        f'id = "{question_id}"\nkind = "metric"\ntext = "A test question."\n'
        f'columns = ["n"]\nkey = ["n"]\nordered = false\nsql = "{sql}"\n'
    )


def questions_dir(tmp_path: Path, dev: str, expected: dict[str, str]) -> Path:
    directory = tmp_path / "questions"
    (directory / "expected").mkdir(parents=True)
    (directory / "dev.toml").write_text(dev, encoding="utf-8")
    (directory / "heldout.toml").write_text("", encoding="utf-8")
    for question_id, text in expected.items():
        (directory / "expected" / f"{question_id}.json").write_text(text, encoding="utf-8")
    return directory


def test_the_stored_answers_match_the_seeded_database(seeded: Settings) -> None:
    code, lines, err = run()

    assert code == 0, err
    assert len(lines) == 12
    assert all(line.startswith("ok ") for line in lines)


def test_drift_is_reported(seeded: Settings, tmp_path: Path) -> None:
    directory = copy_of_questions(tmp_path)
    path = directory / "expected" / f"{ORGANIC}.json"
    rows = json.loads(path.read_text(encoding="utf-8"))["rows"]
    rows[0][0] += 1
    path.write_text(json.dumps({"rows": rows}), encoding="utf-8")

    code, lines, _ = run("--questions-dir", str(directory))

    assert code == 1
    assert f"DRIFT {ORGANIC}" in lines
    assert sum(line.startswith("ok ") for line in lines) == 11


def test_a_missing_expected_file_is_reported(seeded: Settings, tmp_path: Path) -> None:
    directory = copy_of_questions(tmp_path)
    (directory / "expected" / f"{ORGANIC}.json").unlink()

    code, lines, _ = run("--questions-dir", str(directory))

    assert code == 1
    assert f"MISSING {ORGANIC}" in lines


def test_wrong_columns_are_reported(seeded: Settings, tmp_path: Path) -> None:
    directory = questions_dir(
        tmp_path,
        one_question("wrong-columns", "select 1 as other"),
        {"wrong-columns": '{"rows": [[1]]}'},
    )

    code, lines, _ = run("--questions-dir", str(directory))

    assert code == 1
    assert len(lines) == 1
    assert lines[0].startswith("ERROR wrong-columns  ")
    assert "other" in lines[0]


def test_a_failing_query_is_that_questions_error_and_the_next_one_still_runs(
    seeded: Settings, tmp_path: Path
) -> None:
    directory = questions_dir(
        tmp_path,
        one_question("broken", "select n from no_such_table")
        + "\n"
        + one_question("fine", "select 2 as n"),
        {"fine": '{"rows": [[2]]}'},
    )

    code, lines, _ = run("--questions-dir", str(directory))

    assert code == 1
    assert len(lines) == 2
    assert lines[0].startswith("ERROR broken  ")
    assert "no_such_table" in lines[0]
    assert lines[1] == "ok fine"


def test_a_reference_query_cannot_write(seeded: Settings, tmp_path: Path) -> None:
    sql = "with gone as (delete from quality_incident returning 1) select count(*) as n from gone"
    directory = questions_dir(tmp_path, one_question("writer", sql), {})

    code, lines, _ = run("--questions-dir", str(directory))

    assert code == 1
    assert lines[0].startswith("ERROR writer  ")
    with psycopg.connect(seeded.postgres_dsn) as connection:
        row = connection.execute("select count(*) from quality_incident").fetchone()
    assert row == (2,)


def test_write_expected_rewrites_the_stored_answers_byte_for_byte(
    seeded: Settings, tmp_path: Path
) -> None:
    directory = copy_of_questions(tmp_path)
    for stale in (directory / "expected").glob("*.json"):
        stale.unlink()

    code, _, err = run("--questions-dir", str(directory), "--write-expected")

    assert code == 0, err
    stored = sorted((QUESTIONS / "expected").glob("*.json"))
    assert len(stored) == 12
    for path in stored:
        assert (directory / "expected" / path.name).read_text() == path.read_text()


def scalar(connection: psycopg.Connection[Any], sql: str) -> Decimal:
    row = connection.execute(sql).fetchone()
    assert row is not None
    return Decimal(row[0])


def test_the_fruity_question_counts_each_line_once(seeded: Settings) -> None:
    stored = json.loads((QUESTIONS / "expected" / f"{FRUITY}.json").read_text())["rows"]
    with psycopg.connect(seeded.postgres_dsn) as connection:
        direct = scalar(
            connection,
            """
            select sum(ol.kg)
            from order_line ol join sales_order o on o.code = ol.order_code
            where o.ordered_on >= date '2025-01-01' and o.ordered_on < date '2026-01-01'
              and ol.product_code in (
                select pf.product_code from product_flavour pf
                join concept f on f.key = pf.flavour_key
                where f.key = 'flavour.fruity'
                   or f.parent_key = 'flavour.fruity'
                   or f.parent_key in (select key from concept where parent_key = 'flavour.fruity')
              )
            """,
        )
        fanned = scalar(
            connection,
            """
            select sum(ol.kg)
            from order_line ol join sales_order o on o.code = ol.order_code
            join product_flavour pf on pf.product_code = ol.product_code
            join concept_closure cc on cc.descendant_key = pf.flavour_key
            where o.ordered_on >= date '2025-01-01' and o.ordered_on < date '2026-01-01'
              and cc.ancestor_key = 'flavour.fruity'
            """,
        )

    assert len(stored) == 1
    assert Decimal(str(stored[0][0])) == direct.quantize(Decimal("0.001"))
    assert fanned > direct
