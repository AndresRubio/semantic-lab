import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent.parent / "src" / "semantic_lab"
ALLOWED: dict[str, set[str]] = {
    "domain": set(),
    "rdf": {"domain"},
    "seed": {"domain"},
    "evals": {"domain"},
    "semantic": set(),
}


def imported_modules(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module)
            if node.module == "semantic_lab":
                names += [f"semantic_lab.{alias.name}" for alias in node.names]
    return names


def top_level_modules() -> list[Path]:
    return sorted(path for path in SRC.glob("*.py") if path.name != "__init__.py")


def package_of(path: Path) -> str | None:
    parts = path.relative_to(SRC).parts
    return parts[0] if len(parts) > 1 else None


def ours(module: str) -> str | None:
    parts = module.split(".")
    if parts[0] != "semantic_lab" or len(parts) < 2:
        return None
    return parts[1]


def test_each_layer_imports_only_what_the_table_allows() -> None:
    problems = []
    for path in sorted(SRC.rglob("*.py")):
        package = package_of(path)
        if package is None:
            continue
        for module in imported_modules(path):
            target = ours(module)
            if target is None or target == package:
                continue
            if target == "commands":
                problems.append(f"{path.name} imports commands")
            elif package in ALLOWED and target not in ALLOWED[package]:
                problems.append(f"{path.name} ({package}) imports {target}")
    assert problems == []


def test_top_level_modules_do_not_import_commands() -> None:
    modules = top_level_modules()
    assert {path.name for path in modules} >= {"config.py", "probes.py", "redaction.py"}
    problems = [
        f"{path.name} imports {module}"
        for path in modules
        for module in imported_modules(path)
        if ours(module) == "commands"
    ]
    assert problems == []


def test_domain_imports_only_the_standard_library() -> None:
    problems = []
    for path in sorted((SRC / "domain").rglob("*.py")):
        for module in imported_modules(path):
            root = module.split(".")[0]
            if root not in sys.stdlib_module_names and root != "semantic_lab":
                problems.append(f"{path.name} imports {module}")
    assert problems == []


def test_only_the_loader_of_the_seed_package_imports_a_third_party_module() -> None:
    problems = []
    for path in sorted((SRC / "seed").rglob("*.py")):
        if path.name == "load.py":
            continue
        for module in imported_modules(path):
            root = module.split(".")[0]
            if root in sys.stdlib_module_names:
                continue
            if module == "semantic_lab.domain" or module.startswith("semantic_lab.domain."):
                continue
            if module == "semantic_lab.seed" or module.startswith("semantic_lab.seed."):
                continue
            problems.append(f"{path.name} imports {module}")
    assert problems == []
