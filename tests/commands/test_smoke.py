import io
from pathlib import Path

from semantic_lab.commands import smoke
from semantic_lab.probes import Check
from tests.support import envfile

ROOT = Path(__file__).resolve().parent.parent.parent


def down_env() -> dict[str, str]:
    env = envfile.read(ROOT / ".env.example")
    env["SEMANTIC_LAB_POSTGRES_DSN"] = "postgresql://lab:secret@127.0.0.1:1/lab"
    env["SEMANTIC_LAB_NEO4J_URI"] = "bolt://127.0.0.1:1"
    env["SEMANTIC_LAB_CUBE_URL"] = "http://127.0.0.1:1"
    env["SEMANTIC_LAB_OLLAMA_URL"] = "http://127.0.0.1:1"
    return env


def test_report_prints_one_line_per_check_and_returns_0() -> None:
    out = io.StringIO()
    checks = [Check("postgres", True, "select 1"), Check("cube", True, "2 cubes")]
    assert smoke.report(checks, out) == 0
    assert out.getvalue() == "ok    postgres  select 1\nok    cube  2 cubes\n"


def test_one_failed_check_returns_1_and_the_others_still_print() -> None:
    out = io.StringIO()
    checks = [
        Check("postgres", True, "select 1"),
        Check("neo4j", False, "ServiceUnavailable: refused"),
        Check("cube", True, "2 cubes"),
    ]
    assert smoke.report(checks, out) == 1
    assert out.getvalue().splitlines() == [
        "ok    postgres  select 1",
        "FAIL  neo4j  ServiceUnavailable: refused",
        "ok    cube  2 cubes",
    ]


def test_a_missing_setting_exits_2_and_names_it() -> None:
    env = {
        k: v
        for k, v in envfile.read(ROOT / ".env.example").items()
        if k != "SEMANTIC_LAB_CUBE_URL"
    }
    out, err = io.StringIO(), io.StringIO()
    assert smoke.main([], env, out, err) == 2
    assert err.getvalue() == "missing setting: SEMANTIC_LAB_CUBE_URL\n"
    assert out.getvalue() == ""


def test_everything_down_exits_1_with_four_fail_lines() -> None:
    out, err = io.StringIO(), io.StringIO()
    assert smoke.main([], down_env(), out, err) == 1
    lines = out.getvalue().splitlines()
    assert [line.split()[:2] for line in lines] == [
        ["FAIL", "postgres"],
        ["FAIL", "neo4j"],
        ["FAIL", "cube"],
        ["FAIL", "ollama"],
    ]
    assert "secret" not in out.getvalue()
    assert err.getvalue() == ""


def test_no_model_leaves_ollama_out() -> None:
    out, err = io.StringIO(), io.StringIO()
    assert smoke.main(["--no-model"], down_env(), out, err) == 1
    lines = out.getvalue().splitlines()
    assert [line.split()[1] for line in lines] == ["postgres", "neo4j", "cube"]
