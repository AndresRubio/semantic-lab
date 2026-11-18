import json
from pathlib import Path

from semantic_lab.evals import questions

DIRECTORY = Path(__file__).resolve().parent.parent.parent / "questions"
MAX_ROWS = 200


def dev() -> tuple[questions.Question, ...]:
    return questions.load(DIRECTORY / "dev.toml")


def heldout() -> tuple[questions.Question, ...]:
    return questions.load(DIRECTORY / "heldout.toml")


def test_ids_are_unique_across_both_files() -> None:
    ids = [question.id for question in dev() + heldout()]
    assert len(ids) == len(set(ids))


def test_every_question_has_an_expected_file_and_no_file_is_orphaned() -> None:
    ids = {question.id for question in dev() + heldout()}
    stored = {path.stem for path in (DIRECTORY / "expected").glob("*.json")}
    assert stored == ids


def test_every_expected_row_has_one_value_per_column_and_at_most_200_rows() -> None:
    for question in dev() + heldout():
        rows = questions.read_expected(DIRECTORY / "expected", question.id)
        assert 0 < len(rows) <= MAX_ROWS, question.id
        for row in rows:
            assert len(row) == len(question.columns), question.id


def test_there_are_eight_dev_and_four_heldout_questions_or_more() -> None:
    assert len(dev()) >= 8
    assert len(heldout()) >= 4


def test_the_expected_files_are_valid_json_with_a_rows_list() -> None:
    for path in (DIRECTORY / "expected").glob("*.json"):
        assert isinstance(json.loads(path.read_text(encoding="utf-8"))["rows"], list), path.name
