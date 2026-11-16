import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
PINNED = re.compile(r"uses: [\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+$")


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


def test_the_workflow_never_selects_the_model_marker() -> None:
    lines = (WORKFLOWS / "checks.yml").read_text().splitlines()
    assert not [line for line in lines if "-m model" in line]
