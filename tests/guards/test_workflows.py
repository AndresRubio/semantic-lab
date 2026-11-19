import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
PINNED = re.compile(r"uses: [\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+$")
# The value of a pytest -m option: quoted with " or ', unquoted, or joined with =.
MARKER_OPTION = re.compile(r"""(?:^|\s)-m(?:=|\s+)(?:"([^"]*)"|'([^']*)'|(\S+))""")
# The word model in a marker expression, unless a `not ` stands directly before it.
SELECTED_MODEL = re.compile(r"(?<!not )\bmodel\b")


def selects_model(line: str) -> bool:
    """Whether a command line passes a -m expression that can select the model marker."""
    for option in MARKER_OPTION.finditer(line):
        expression = next(group for group in option.groups() if group is not None)
        if SELECTED_MODEL.search(expression):
            return True
    return False


def workflow_files() -> list[Path]:
    files = sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])
    assert files, f"no workflow file in {WORKFLOWS}"
    return files


def test_every_action_is_pinned_to_a_commit_with_its_version() -> None:
    uses = 0
    for path in workflow_files():
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if "uses:" not in line:
                continue
            uses += 1
            assert PINNED.search(line.strip().removeprefix("- ")), f"{path.name}:{number}: {line}"
    assert uses > 0


def test_no_workflow_selects_the_model_marker() -> None:
    for path in workflow_files():
        selecting = [line for line in path.read_text().splitlines() if selects_model(line)]
        assert not selecting, f"{path.name}: {selecting}"


@pytest.mark.parametrize(
    "line",
    [
        "pytest -m model",
        'pytest -m "model"',
        "pytest -m 'model'",
        "pytest -m=model",
        'pytest -m "db or model"',
    ],
)
def test_the_pattern_catches_every_way_to_select_the_model_marker(line: str) -> None:
    assert selects_model(line)


@pytest.mark.parametrize(
    "line",
    [
        'pytest -n auto -m "not db and not model"',
        "pytest -m db",
        "uv run mypy",
    ],
)
def test_the_pattern_lets_the_other_lines_through(line: str) -> None:
    assert not selects_model(line)


def test_a_workflow_runs_the_ontology_command_over_every_order() -> None:
    # The suite validates the first 200 orders, so a rule that only later rows break needs this.
    runs = [
        line.strip()
        for path in workflow_files()
        for line in path.read_text().splitlines()
        if line.strip().startswith("- run:")
    ]
    assert [r for r in runs if "semantic_lab.commands.ontology" in r and "--full" in r]
