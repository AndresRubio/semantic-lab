from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from semantic_lab.evals import questions
from semantic_lab.evals.questions import MissingAnswer, Question, QuestionError

VALID = """
[[question]]
id = "metric-one"
kind = "metric"
text = "How many lots are there? Give the number as lots."
columns = ["lots"]
key = ["lots"]
ordered = false
sql = "select 1 as lots"
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "q.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_reads_a_question(tmp_path: Path) -> None:
    loaded = questions.load(write(tmp_path, VALID))

    assert loaded == (
        Question(
            id="metric-one",
            kind="metric",
            text="How many lots are there? Give the number as lots.",
            columns=("lots",),
            key=("lots",),
            ordered=False,
            sql="select 1 as lots",
        ),
    )


def test_kinds_are_the_four_the_design_names() -> None:
    assert questions.KINDS == ("metric", "path", "hierarchy", "mixed")


CASES = {
    "a duplicate id": VALID + VALID,
    "a kind outside KINDS": VALID.replace('kind = "metric"', 'kind = "other"'),
    "a key column missing from columns": VALID.replace('key = ["lots"]', 'key = ["nope"]'),
    "empty text": VALID.replace(
        'text = "How many lots are there? Give the number as lots."', 'text = ""'
    ),
    "empty sql": VALID.replace('sql = "select 1 as lots"', 'sql = ""'),
    "no columns": VALID.replace('columns = ["lots"]', "columns = []").replace(
        'key = ["lots"]', "key = []"
    ),
    "an empty key": VALID.replace('key = ["lots"]', "key = []"),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_load_refuses(tmp_path: Path, case: str) -> None:
    with pytest.raises(QuestionError, match="metric-one"):
        questions.load(write(tmp_path, CASES[case]))


@pytest.mark.parametrize("text", ["", "# only a comment\n", "question = []\n"])
def test_load_refuses_a_file_with_no_questions(tmp_path: Path, text: str) -> None:
    with pytest.raises(QuestionError, match=r"q\.toml.*no questions"):
        questions.load(write(tmp_path, text))


def test_load_refuses_a_file_that_is_not_toml(tmp_path: Path) -> None:
    with pytest.raises(QuestionError, match="q.toml"):
        questions.load(write(tmp_path, "this is = not [toml"))


def test_load_refuses_a_file_that_does_not_exist(tmp_path: Path) -> None:
    with pytest.raises(QuestionError, match="missing.toml"):
        questions.load(tmp_path / "missing.toml")


def test_to_json_rows() -> None:
    rows = questions.to_json_rows(
        [[Decimal("12.50"), Decimal("3"), Decimal("3.000"), date(2025, 3, 18), "Peru", 7]]
    )

    assert rows == [[12.5, 3, 3, "2025-03-18", "Peru", 7]]
    assert type(rows[0][0]) is float
    assert type(rows[0][1]) is int
    assert type(rows[0][2]) is int


def test_read_expected_reads_the_rows(tmp_path: Path) -> None:
    (tmp_path / "metric-one.json").write_text('{"rows": [["a", 1.5], ["b", 2]]}', encoding="utf-8")

    assert questions.read_expected(tmp_path, "metric-one") == [["a", 1.5], ["b", 2]]


def test_read_expected_of_a_missing_file_raises_missing_answer(tmp_path: Path) -> None:
    with pytest.raises(MissingAnswer, match="metric-one"):
        questions.read_expected(tmp_path, "metric-one")


def test_a_missing_answer_is_a_question_error() -> None:
    assert issubclass(MissingAnswer, QuestionError)


@pytest.mark.parametrize("text", ['{"nope": 1}', '{"rows": [', "", '{"rows": [1, 2]}', "[]"])
def test_read_expected_of_a_file_that_exists_but_is_unusable_is_not_a_missing_answer(
    tmp_path: Path, text: str
) -> None:
    (tmp_path / "metric-one.json").write_text(text, encoding="utf-8")

    with pytest.raises(QuestionError, match="metric-one") as raised:
        questions.read_expected(tmp_path, "metric-one")
    assert not isinstance(raised.value, MissingAnswer)


def test_read_expected_of_a_directory_in_place_of_the_file_is_not_a_missing_answer(
    tmp_path: Path,
) -> None:
    (tmp_path / "metric-one.json").mkdir()

    with pytest.raises(QuestionError, match="metric-one") as raised:
        questions.read_expected(tmp_path, "metric-one")
    assert not isinstance(raised.value, MissingAnswer)
