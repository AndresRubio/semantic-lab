"""The evaluation questions: their TOML files, their stored answers and the JSON form of a row."""

import json
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

KINDS = ("metric", "path", "hierarchy", "mixed")


class QuestionError(Exception):
    """A question file, a stored answer or a reference query that cannot be used."""


class MissingAnswer(QuestionError):
    """A question whose stored answer file does not exist."""


@dataclass(frozen=True)
class Question:
    id: str
    kind: str
    text: str
    columns: tuple[str, ...]
    key: tuple[str, ...]
    ordered: bool
    sql: str


def _strings(raw: dict[str, object], field: str, label: str) -> tuple[str, ...]:
    value = raw.get(field)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise QuestionError(f"question {label}: {field} must be a list of strings")
    return tuple(value)


def _text(raw: dict[str, object], field: str, label: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise QuestionError(f"question {label}: {field} must be a non-empty string")
    return value


def _build(raw: dict[str, object], position: int) -> Question:
    identifier = raw.get("id")
    if not isinstance(identifier, str) or not identifier:
        raise QuestionError(f"question number {position}: id must be a non-empty string")
    kind = _text(raw, "kind", identifier)
    if kind not in KINDS:
        raise QuestionError(f"question {identifier}: kind {kind!r} is not one of {KINDS}")
    columns = _strings(raw, "columns", identifier)
    if not columns:
        raise QuestionError(f"question {identifier}: columns is empty")
    key = _strings(raw, "key", identifier)
    if not key:
        raise QuestionError(f"question {identifier}: key is empty, so no column identifies a row")
    for name in key:
        if name not in columns:
            raise QuestionError(f"question {identifier}: key column {name} is not in columns")
    ordered = raw.get("ordered")
    if not isinstance(ordered, bool):
        raise QuestionError(f"question {identifier}: ordered must be true or false")
    return Question(
        id=identifier,
        kind=kind,
        text=_text(raw, "text", identifier),
        columns=columns,
        key=key,
        ordered=ordered,
        sql=_text(raw, "sql", identifier),
    )


def load(path: Path) -> tuple[Question, ...]:
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise QuestionError(f"cannot read {path}: {type(error).__name__}") from error
    except tomllib.TOMLDecodeError as error:
        raise QuestionError(f"{path} is not valid TOML: {error}") from error
    raw_questions = document.get("question", [])
    if not isinstance(raw_questions, list):
        raise QuestionError(f"{path}: question must be an array of tables")
    if not raw_questions:
        raise QuestionError(f"{path} holds no questions")
    built: list[Question] = []
    for position, raw in enumerate(raw_questions, start=1):
        built.append(_build(raw, position))
    seen: set[str] = set()
    for question in built:
        if question.id in seen:
            raise QuestionError(f"question {question.id} appears twice in {path}")
        seen.add(question.id)
    return tuple(built)


def read_expected(directory: Path, question_id: str) -> list[list[object]]:
    path = directory / f"{question_id}.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise MissingAnswer(f"question {question_id}: no stored answer at {path}") from error
    except OSError as error:
        raise QuestionError(
            f"question {question_id}: cannot read {path}: {type(error).__name__}"
        ) from error
    except ValueError as error:
        # A JSONDecodeError, or bytes that are not UTF-8: both are ValueError.
        raise QuestionError(f"question {question_id}: {path} is not valid JSON") from error
    rows = document.get("rows") if isinstance(document, dict) else None
    if not isinstance(rows, list) or not all(isinstance(row, list) for row in rows):
        raise QuestionError(f"question {question_id}: {path} must hold a rows list of lists")
    return rows


def _json_value(value: object) -> object:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def to_json_rows(rows: Iterable[Sequence[object]]) -> list[list[object]]:
    """Rows as JSON holds them: a whole Decimal is an int, another Decimal a float, a date its
    ISO text. The reference queries round in SQL, so a Decimal here has at most 3 places."""
    return [[_json_value(value) for value in row] for row in rows]
