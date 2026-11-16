import io
import re
import shutil
from pathlib import Path

import psycopg

from semantic_lab.commands import seed
from tests.support import envfile

ROOT = Path(__file__).resolve().parent.parent.parent
TAXONOMY = ROOT / "ontology" / "taxonomy"
PASSWORD = "hunter2-secret"


def down_env() -> dict[str, str]:
    env = envfile.read(ROOT / ".env.example")
    env["SEMANTIC_LAB_POSTGRES_DSN"] = f"postgresql://lab:{PASSWORD}@127.0.0.1:1/lab"
    return env


def test_a_missing_setting_exits_2_and_names_it() -> None:
    env = {
        k: v
        for k, v in envfile.read(ROOT / ".env.example").items()
        if k != "SEMANTIC_LAB_POSTGRES_DSN"
    }
    out, err = io.StringIO(), io.StringIO()
    assert seed.main([], env, out, err) == 2
    assert err.getvalue() == "missing setting: SEMANTIC_LAB_POSTGRES_DSN\n"
    assert out.getvalue() == ""


def test_a_broken_taxonomy_exits_1_before_any_connection(tmp_path: Path) -> None:
    (tmp_path / "bad.ttl").write_text(
        "@prefix skos: <http://www.w3.org/2004/02/skos/core#> .\n"
        "<http://example.org/a> a skos:Concept .\n",
        encoding="utf-8",
    )
    out, err = io.StringIO(), io.StringIO()
    code = seed.main(["--taxonomy-dir", str(tmp_path)], down_env(), out, err)
    assert code == 1
    assert err.getvalue().startswith("taxonomy: ")
    assert len(err.getvalue().splitlines()) == 1
    assert out.getvalue() == ""


def test_a_taxonomy_dir_that_does_not_exist_exits_1(tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    code = seed.main(["--taxonomy-dir", str(tmp_path / "missing")], down_env(), out, err)
    assert code == 1
    assert err.getvalue().startswith("taxonomy: ")


def test_postgres_down_exits_1_with_one_line_and_no_password() -> None:
    out, err = io.StringIO(), io.StringIO()
    assert seed.main([], down_env(), out, err) == 1
    assert err.getvalue().startswith("postgres: ")
    assert len(err.getvalue().splitlines()) == 1
    assert PASSWORD not in out.getvalue() + err.getvalue()
    assert out.getvalue() == ""


def test_an_unparsable_dsn_is_not_quoted() -> None:
    env = down_env()
    env["SEMANTIC_LAB_POSTGRES_DSN"] = "postgresql://lab:pa%zzword@127.0.0.1:1/lab"
    out, err = io.StringIO(), io.StringIO()
    assert seed.main([], env, out, err) == 1
    assert err.getvalue() == "postgres: ProgrammingError: invalid DSN\n"


def test_a_taxonomy_file_with_a_syntax_error_exits_1_before_any_connection(
    tmp_path: Path,
) -> None:
    (tmp_path / "bad.ttl").write_text("this is not turtle {{{", encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    code = seed.main(["--taxonomy-dir", str(tmp_path)], down_env(), out, err)
    assert code == 1
    assert err.getvalue().startswith("taxonomy: ")
    assert len(err.getvalue().splitlines()) == 1
    assert "Traceback" not in err.getvalue()
    assert out.getvalue() == ""


class FakeConnection:
    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *exc: object) -> None:
        return None


def test_a_programming_error_in_the_rebuild_is_reported_as_itself(monkeypatch) -> None:
    def fail(*args: object) -> dict[str, int]:
        raise psycopg.errors.UndefinedTable("relation \"concept\" does not exist")

    monkeypatch.setattr(seed.psycopg, "connect", lambda dsn: FakeConnection())
    monkeypatch.setattr(seed.load, "rebuild", fail)
    out, err = io.StringIO(), io.StringIO()
    assert seed.main([], down_env(), out, err) == 1
    assert err.getvalue() == 'postgres: UndefinedTable: relation "concept" does not exist\n'
    assert "invalid DSN" not in err.getvalue()
    assert out.getvalue() == ""


def test_a_taxonomy_the_generator_cannot_use_exits_1_with_one_line_before_any_connection(
    tmp_path: Path,
) -> None:
    for source in TAXONOMY.glob("*.ttl"):
        shutil.copy(source, tmp_path / source.name)
    geo = tmp_path / "geo.ttl"
    blocks = re.split(r"\n\n", geo.read_text(encoding="utf-8"))
    removed = ("geo:ethiopia ", "geo:yirgacheffe ", "geo:sidama ", "geo:guji ", "geo:harrar ")
    kept = [block for block in blocks if not block.startswith(removed)]
    assert len(kept) == len(blocks) - len(removed)
    geo.write_text("\n\n".join(kept), encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    code = seed.main(["--taxonomy-dir", str(tmp_path)], down_env(), out, err)
    assert code == 1
    assert err.getvalue().startswith("seed: ")
    assert len(err.getvalue().splitlines()) == 1
    assert "postgres:" not in err.getvalue()
    assert out.getvalue() == ""
