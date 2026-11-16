import io
from pathlib import Path

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
