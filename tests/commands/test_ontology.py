import io
import shutil
from pathlib import Path
from typing import NamedTuple

import pytest

from semantic_lab.commands import ontology
from semantic_lab.domain.records import Dataset
from semantic_lab.domain.sample import first_orders

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


def edit(file: Path, old: str, new: str) -> None:
    text = file.read_text(encoding="utf-8")
    assert old in text, f"{old!r} is not in {file.name}"
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


NAMES = ["taxonomy shapes", "ontology shapes", "mapping", "data shapes"]


class Block(NamedTuple):
    """One check as printed: its status, what it covers and its indented problem lines."""

    name: str
    status: str
    covered: str
    problems: list[str]


def blocks(out: str) -> list[Block]:
    """The checks in the order printed, one per line that is not indented."""
    found: list[Block] = []
    for line in out.splitlines():
        if line.startswith("  "):
            found[-1].problems.append(line.strip())
        else:
            found.append(Block(line[6:23].strip(), line[:6].strip(), line[24:], []))
    return found


def statuses(out: str) -> dict[str, str]:
    """The status of each check by its name."""
    return {block.name: block.status for block in blocks(out)}


def assert_the_export_did_not_run(code: int, out: str, err: str, named: str) -> None:
    assert code == 1
    assert "Traceback" not in err
    assert [block.name for block in blocks(out)] == NAMES
    lines = out.splitlines()
    mapping = next(i for i, line in enumerate(lines) if line.startswith("FAIL  mapping"))
    data = next(i for i, line in enumerate(lines) if line.startswith("FAIL  data shapes"))
    assert any(named in line for line in lines[mapping + 1 : data])
    assert lines[data].endswith("not run")
    assert lines[data + 1 :] == ["  the mapping check failed"]


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
    assert any(
        line.startswith("FAIL  data shapes") and line.endswith("not run")
        for line in out.splitlines()
    )


def test_a_misspelt_column_fails_the_mapping_check_and_skips_the_export(tmp_path: Path) -> None:
    folder = copy_folder(tmp_path)
    edit(folder / "mapping.yaml", "[lot.weight_kg]", "[lot.weight_kgs]")
    code, out, err = run("--ontology-dir", str(folder), "--orders", "5")
    assert_the_export_did_not_run(code, out, err, "weight_kgs")


def test_a_misspelt_property_term_fails_the_mapping_check_and_skips_the_export(
    tmp_path: Path,
) -> None:
    folder = copy_folder(tmp_path)
    edit(folder / "mapping.yaml", "  sl:share:", "  sl:shares:")
    code, out, err = run("--ontology-dir", str(folder), "--orders", "5")
    assert_the_export_did_not_run(code, out, err, "shares")


def test_an_ontology_fault_fails_the_ontology_check_only(tmp_path: Path) -> None:
    folder = copy_folder(tmp_path)
    edit(folder / "ontology.ttl", '"Cooperative"@en, "Cooperativa"@es', '"Cooperative"@en')
    code, out, err = run("--ontology-dir", str(folder), "--orders", "5")
    assert (code, err) == (1, "")
    assert statuses(out) == {
        "taxonomy shapes": "ok",
        "ontology shapes": "FAIL",
        "mapping": "ok",
        "data shapes": "ok",
    }


def test_a_taxonomy_fault_fails_the_taxonomy_check_only(tmp_path: Path) -> None:
    folder = copy_folder(tmp_path)
    taxonomy = folder / "taxonomy" / "process.ttl"
    text = taxonomy.read_text(encoding="utf-8")
    taxonomy.write_text(text + 'process:washed skos:altLabel "voie humide"@fr .\n', encoding="utf-8")
    code, out, err = run("--ontology-dir", str(folder), "--orders", "5")
    assert (code, err) == (1, "")
    assert statuses(out) == {
        "taxonomy shapes": "FAIL",
        "ontology shapes": "ok",
        "mapping": "ok",
        "data shapes": "ok",
    }


def test_an_undeclared_prefix_in_a_sparql_rule_exits_1_with_one_line_on_stderr(
    tmp_path: Path,
) -> None:
    folder = copy_folder(tmp_path)
    edit(folder / "shapes.ttl", "$this skos:notation ?value .", "$this nope:notation ?value .")
    code, out, err = run("--ontology-dir", str(folder), "--orders", "5")
    assert (code, out) == (1, "")
    assert err.startswith("ontology:")
    assert err.count("\n") == 1
    assert "Traceback" not in err


def test_a_negative_order_count_is_a_usage_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        run("--orders", "-1")
    assert raised.value.code == 2
    assert "usage: ontology" in capsys.readouterr().err


def test_zero_orders_is_accepted() -> None:
    code, out, err = run("--orders", "0")
    assert (code, err) == (0, "")
    assert out.splitlines()[3].endswith("from the first 0 orders")


def test_the_data_line_counts_the_orders_the_sample_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def three(dataset: Dataset, count: int) -> Dataset:
        return first_orders(dataset, min(count, 3))

    monkeypatch.setattr(ontology, "first_orders", three)
    code, out, _ = run("--orders", "5")
    assert code == 0
    assert out.splitlines()[3].endswith("from the first 3 orders")


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


Fault = tuple[str, str, str]  # the file, the text to find and its replacement
NO_SPANISH_LABEL: Fault = ("taxonomy/geo.ttl", '"Ethiopia"@en, "Etiopía"@es', '"Ethiopia"@en')
SECOND_DOMAIN: Fault = (
    "ontology.ttl",
    "sl:inRegion a owl:ObjectProperty ;",
    "sl:inRegion a owl:ObjectProperty ;\n    rdfs:domain sl:Farm ;",
)
WASHED_ABOVE_NATURAL: Fault = (
    "taxonomy/process.ttl",
    "process:washed a skos:Concept ;",
    "process:washed a skos:Concept ;\n    skos:broader process:natural ;",
)
NATURAL_ABOVE_WASHED: Fault = (
    "taxonomy/process.ttl",
    "process:natural a skos:Concept ;",
    "process:natural a skos:Concept ;\n    skos:broader process:washed ;",
)
PRODUCT_BELOW_BLEND: Fault = (
    "ontology.ttl",
    "sl:Product a owl:Class ;",
    "sl:Product a owl:Class ;\n    rdfs:subClassOf sl:Blend ;",
)

def run_on_broken_copy(tmp_path: Path, *faults: Fault) -> dict[str, Block]:
    """Apply the faults to a copy of the folder, run the command and return its four checks."""
    folder = copy_folder(tmp_path)
    for name, old, new in faults:
        edit(folder / name, old, new)
    code, out, err = run("--ontology-dir", str(folder), "--orders", "5")
    assert (code, err) == (1, "")
    found = blocks(out)
    assert [block.name for block in found] == NAMES
    return {block.name: block for block in found}


def status_of(found: dict[str, Block]) -> list[str]:
    return [block.status for block in found.values()]


def test_a_missing_spanish_label_is_reported_by_the_loader_line_and_by_the_shape(
    tmp_path: Path,
) -> None:
    found = run_on_broken_copy(tmp_path, NO_SPANISH_LABEL)
    assert status_of(found) == ["FAIL", "ok", "FAIL", "FAIL"]
    problems = found["taxonomy shapes"].problems
    assert [line.startswith("loader:") for line in problems] == [True, False]
    assert "taxonomy/geo#ethiopia MinCountConstraintComponent" in problems[1]
    assert found["mapping"][2:] == ("not run", ["the taxonomy check failed"])
    assert found["data shapes"][2:] == ("not run", ["the mapping check failed"])


def test_a_second_domain_is_reported_by_the_loader_line_and_by_the_shape(tmp_path: Path) -> None:
    found = run_on_broken_copy(tmp_path, SECOND_DOMAIN)
    assert status_of(found) == ["ok", "FAIL", "FAIL", "FAIL"]
    problems = found["ontology shapes"].problems
    assert [line.startswith("loader:") for line in problems] == [True, False]
    assert "inRegion MaxCountConstraintComponent" in problems[1]
    assert found["mapping"][2:] == ("not run", ["the ontology check failed"])
    assert found["data shapes"][2:] == ("not run", ["the mapping check failed"])


def test_a_taxonomy_cycle_only_the_loader_refuses_is_one_loader_line(tmp_path: Path) -> None:
    found = run_on_broken_copy(tmp_path, WASHED_ABOVE_NATURAL, NATURAL_ABOVE_WASHED)
    assert status_of(found) == ["FAIL", "ok", "FAIL", "FAIL"]
    problems = found["taxonomy shapes"].problems
    assert len(problems) == 1
    assert problems[0].startswith("loader:")
    assert "cycle" in problems[0]
    assert found["mapping"][2:] == ("not run", ["the taxonomy check failed"])
    assert found["data shapes"][2:] == ("not run", ["the mapping check failed"])


def test_an_ontology_cycle_only_the_loader_refuses_is_one_loader_line(tmp_path: Path) -> None:
    found = run_on_broken_copy(tmp_path, PRODUCT_BELOW_BLEND)
    assert status_of(found) == ["ok", "FAIL", "FAIL", "FAIL"]
    problems = found["ontology shapes"].problems
    assert len(problems) == 1
    assert problems[0].startswith("loader:")
    assert "cycle" in problems[0]
    assert found["mapping"][2:] == ("not run", ["the ontology check failed"])
    assert found["data shapes"][2:] == ("not run", ["the mapping check failed"])


def test_the_mapping_names_both_absent_values_taxonomy_first(tmp_path: Path) -> None:
    found = run_on_broken_copy(tmp_path, NO_SPANISH_LABEL, SECOND_DOMAIN)
    assert status_of(found) == ["FAIL", "FAIL", "FAIL", "FAIL"]
    assert found["mapping"][2:] == (
        "not run",
        ["the taxonomy check failed", "the ontology check failed"],
    )
    assert found["data shapes"][2:] == ("not run", ["the mapping check failed"])


FRENCH_LABEL: Fault = (
    "taxonomy/process.ttl",
    "process:honey a skos:Concept ;",
    'process:honey a skos:Concept ;\n    skos:altLabel "miel"@fr ;',
)


def test_a_loader_refusal_shows_beside_a_violation_it_has_nothing_to_do_with(
    tmp_path: Path,
) -> None:
    found = run_on_broken_copy(tmp_path, FRENCH_LABEL, WASHED_ABOVE_NATURAL, NATURAL_ABOVE_WASHED)
    assert status_of(found) == ["FAIL", "ok", "FAIL", "FAIL"]
    problems = found["taxonomy shapes"].problems
    assert len(problems) == 2
    assert problems[0].startswith("loader:") and "cycle" in problems[0]
    assert "process#honey LanguageInConstraintComponent" in problems[1]


def test_the_loader_line_survives_the_cap_on_shown_problems(tmp_path: Path) -> None:
    folder = copy_folder(tmp_path)
    file = folder / "taxonomy" / "process.ttl"
    text = file.read_text(encoding="utf-8")
    extra = "".join(f'process:washed skos:altLabel "x{i}"@fr .\n' for i in range(25))
    file.write_text(text + extra, encoding="utf-8")
    edit(file, *WASHED_ABOVE_NATURAL[1:])
    edit(file, *NATURAL_ABOVE_WASHED[1:])
    code, out, err = run("--ontology-dir", str(folder), "--orders", "5")
    problems = blocks(out)[0].problems
    assert (code, err) == (1, "")
    assert [line.startswith("loader:") for line in problems[:2]] == [True, False]
    assert len(problems) == 21
    assert problems[-1] == "and 6 more"


UNKNOWN_KEY: Fault = ("mapping.yaml", "{columns: [lot.weight_kg]}", "{colums: [lot.weight_kg]}")
TERM_TWICE: Fault = (
    "mapping.yaml",
    "  sl:weightKg:\n",
    "  sl:weightKg:\n    postgres: {columns: [lot.variety]}\n  sl:weightKg:\n",
)


@pytest.mark.parametrize(
    ("fault", "named"),
    [(UNKNOWN_KEY, "the unknown key 'colums'"), (TERM_TWICE, "the key 'sl:weightKg' appears twice")],
)
def test_a_mapping_file_the_reader_refuses_fails_the_mapping_check_only(
    tmp_path: Path, fault: Fault, named: str
) -> None:
    found = run_on_broken_copy(tmp_path, fault)
    assert status_of(found) == ["ok", "ok", "FAIL", "FAIL"]
    assert found["mapping"].covered == "not read"
    assert len(found["mapping"].problems) == 1
    assert found["mapping"].problems[0].startswith("mapping.yaml: ")
    assert named in found["mapping"].problems[0]
    assert found["data shapes"][2:] == ("not run", ["the mapping check failed"])


def test_a_missing_mapping_file_fails_the_mapping_check_only(tmp_path: Path) -> None:
    folder = copy_folder(tmp_path)
    (folder / "mapping.yaml").unlink()
    code, out, err = run("--ontology-dir", str(folder), "--orders", "5")
    assert (code, err) == (1, "")
    assert [(block.status, block.covered) for block in blocks(out)][2] == ("FAIL", "not read")


NAME_FOR_REGION: Fault = (
    "mapping.yaml",
    "{columns: [cooperative.region_key]}",
    "{columns: [cooperative.name]}",
)
REGION_FOR_NAME: Fault = (
    "mapping.yaml",
    "{columns: [cooperative.name, farm.name",
    "{columns: [cooperative.region_key, farm.name",
)


def test_two_text_columns_swapped_fail_the_export_with_one_line(tmp_path: Path) -> None:
    found = run_on_broken_copy(tmp_path, NAME_FOR_REGION, REGION_FOR_NAME)
    assert status_of(found) == ["ok", "ok", "ok", "FAIL"]
    assert len(found["data shapes"].problems) == 1
    line = found["data shapes"].problems[0]
    assert line.startswith("export: property https://semantic-lab.example/ontology#inRegion: ")
    assert "column cooperative.name holds" in line
    assert line.endswith("which is no concept key")


NUMBER_FOR_TEXT: Fault = (
    "mapping.yaml",
    "sl:variety:\n    postgres: {columns: [lot.variety]}",
    "sl:variety:\n    postgres: {columns: [farm.altitude_m]}",
)
TEXT_FOR_NUMBER: Fault = (
    "mapping.yaml",
    "sl:altitudeMetres:\n    postgres: {columns: [farm.altitude_m]}",
    "sl:altitudeMetres:\n    postgres: {columns: [lot.variety]}",
)


def test_a_column_under_a_property_of_another_class_and_type_fails_the_mapping_check(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    found = run_on_broken_copy(tmp_path, TEXT_FOR_NUMBER, NUMBER_FOR_TEXT)
    assert status_of(found) == ["ok", "ok", "FAIL", "FAIL"]
    problems = found["mapping"].problems
    assert any("altitudeMetres: column lot.variety holds str" in line for line in problems)
    assert any("altitudeMetres: column lot.variety is on the table of" in line for line in problems)
    assert found["data shapes"][2:] == ("not run", ["the mapping check failed"])
    # rdflib logs a traceback for each literal whose text does not fit its datatype.
    assert caplog.records == []


MISSPELT_TYPE: Fault = (
    "ontology.ttl",
    "sl:inRegion a owl:ObjectProperty ;",
    "sl:inRegion a owl:ObjectPropery ;",
)


def test_a_term_with_a_misspelt_type_fails_the_ontology_check(tmp_path: Path) -> None:
    found = run_on_broken_copy(tmp_path, MISSPELT_TYPE)
    assert status_of(found) == ["ok", "FAIL", "FAIL", "FAIL"]
    problems = found["ontology shapes"].problems
    assert len(problems) == 1
    assert problems[0].startswith("https://semantic-lab.example/ontology#inRegion OrConstraint")
