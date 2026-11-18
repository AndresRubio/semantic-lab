import io
import shutil
from pathlib import Path

from semantic_lab.commands import ontology

ROOT = Path(__file__).resolve().parent.parent.parent
FOLDER = ROOT / "ontology"


def run(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = ontology.main(list(argv), out, err)
    return code, out.getvalue(), err.getvalue()


def copy_folder(tmp_path: Path) -> Path:
    target = tmp_path / "ontology"
    shutil.copytree(FOLDER, target)
    return target


def test_the_repository_folder_passes_all_four_checks() -> None:
    code, out, err = run("--orders", "20")
    lines = out.splitlines()
    assert (code, err) == (0, "")
    assert len(lines) == 4
    assert all(line.startswith("ok") for line in lines)
    assert "from the first 20 orders" in lines[3]


def test_two_runs_print_the_same_text() -> None:
    assert run("--orders", "5") == run("--orders", "5")


def test_a_mapping_without_sl_share_fails_the_mapping_check(tmp_path: Path) -> None:
    folder = copy_folder(tmp_path)
    mapping = folder / "mapping.yaml"
    lines = mapping.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith("  sl:share:"))
    end = next(
        (i for i in range(start + 1, len(lines)) if not lines[i].startswith("   ")), len(lines)
    )
    mapping.write_text("".join(lines[:start] + lines[end:]), encoding="utf-8")
    code, out, err = run("--ontology-dir", str(folder), "--orders", "5")
    assert (code, err) == (1, "")
    assert any(line.startswith("FAIL  mapping") for line in out.splitlines())
    assert "sl:share" in out or "roast_batch_lot.share" in out


def test_cut_shapes_exit_1_with_one_line_on_stderr(tmp_path: Path) -> None:
    folder = copy_folder(tmp_path)
    shapes = folder / "shapes.ttl"
    text = shapes.read_text(encoding="utf-8")
    shapes.write_text(text[: len(text) // 2], encoding="utf-8")
    code, _, err = run("--ontology-dir", str(folder), "--orders", "5")
    assert code == 1
    assert err.startswith("ontology:")
    assert err.count("\n") == 1
    assert "Traceback" not in err


def test_a_missing_folder_exits_1_with_one_line_on_stderr(tmp_path: Path) -> None:
    code, out, err = run("--ontology-dir", str(tmp_path / "nope"))
    assert code == 1
    assert err.startswith("ontology:")
    assert err.count("\n") == 1
    assert out == ""
