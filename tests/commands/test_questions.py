import io
import shutil
from pathlib import Path

import pytest

from semantic_lab.commands import questions
from tests.support import envfile

ROOT = Path(__file__).resolve().parent.parent.parent
STACK_ENV = ROOT / "tests" / "stack.env"
PASSWORD = "hunter2-secret"


def down_env() -> dict[str, str]:
    env = envfile.read(STACK_ENV)
    env["SEMANTIC_LAB_POSTGRES_DSN"] = f"postgresql://lab:{PASSWORD}@127.0.0.1:1/lab"
    return env


def test_a_missing_setting_exits_2() -> None:
    env = {k: v for k, v in envfile.read(STACK_ENV).items() if k != "SEMANTIC_LAB_POSTGRES_DSN"}
    out, err = io.StringIO(), io.StringIO()

    assert questions.main([], env, out, err) == 2
    assert err.getvalue() == "missing setting: SEMANTIC_LAB_POSTGRES_DSN\n"
    assert out.getvalue() == ""


def test_a_questions_directory_without_the_files_exits_1_before_any_connection(
    tmp_path: Path,
) -> None:
    out, err = io.StringIO(), io.StringIO()

    code = questions.main(["--questions-dir", str(tmp_path)], down_env(), out, err)

    assert code == 1
    assert err.getvalue().startswith("questions: ")
    assert len(err.getvalue().splitlines()) == 1
    assert out.getvalue() == ""


def test_postgres_down_exits_1_with_one_line_and_no_password() -> None:
    out, err = io.StringIO(), io.StringIO()

    code = questions.main(["--questions-dir", str(ROOT / "questions")], down_env(), out, err)

    assert code == 1
    assert err.getvalue().startswith("postgres: ")
    assert len(err.getvalue().splitlines()) == 1
    assert "Traceback" not in err.getvalue()
    assert PASSWORD not in out.getvalue() + err.getvalue()
    assert out.getvalue() == ""


def test_an_unparsable_dsn_is_not_quoted() -> None:
    env = down_env()
    env["SEMANTIC_LAB_POSTGRES_DSN"] = "postgresql://lab:pa%zzword@127.0.0.1:1/lab"
    out, err = io.StringIO(), io.StringIO()

    code = questions.main(["--questions-dir", str(ROOT / "questions")], env, out, err)

    assert code == 1
    assert err.getvalue() == "postgres: ProgrammingError: invalid DSN\n"


class FakeConnection:
    read_only = False

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def rollback(self) -> None:
        return None


def test_a_write_failure_is_reported_in_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in questions.FILES:
        shutil.copy(ROOT / "questions" / name, tmp_path / name)
    (tmp_path / "expected").write_text("a file where the directory should be", encoding="utf-8")
    monkeypatch.setattr(questions.psycopg, "connect", lambda dsn: FakeConnection())
    monkeypatch.setattr(questions.reference, "run_sql", lambda connection, question: [[1]])
    out, err = io.StringIO(), io.StringIO()

    code = questions.main(
        ["--questions-dir", str(tmp_path), "--write-expected"], down_env(), out, err
    )

    assert code == 1
    assert err.getvalue().startswith("questions: FileExistsError: ")
    assert len(err.getvalue().splitlines()) == 1
    assert "Traceback" not in err.getvalue()
