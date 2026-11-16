import subprocess
from pathlib import Path

from tests.support import envfile

ROOT = Path(__file__).resolve().parent.parent.parent
FILES = {"example": ROOT / ".env.example", "stack": ROOT / "tests" / "stack.env"}
PORT_KEYS = [
    "SEMANTIC_LAB_POSTGRES_PORT",
    "SEMANTIC_LAB_NEO4J_HTTP_PORT",
    "SEMANTIC_LAB_NEO4J_BOLT_PORT",
    "SEMANTIC_LAB_CUBE_PORT",
]


def test_both_files_have_the_same_keys() -> None:
    assert set(envfile.read(FILES["example"])) == set(envfile.read(FILES["stack"]))


def test_each_dsn_and_address_matches_its_parts() -> None:
    for path in FILES.values():
        env = envfile.read(path)
        user = env["SEMANTIC_LAB_POSTGRES_USER"]
        password = env["SEMANTIC_LAB_POSTGRES_PASSWORD"]
        db = env["SEMANTIC_LAB_POSTGRES_DB"]
        pg_port = env["SEMANTIC_LAB_POSTGRES_PORT"]
        assert env["SEMANTIC_LAB_POSTGRES_DSN"] == (
            f"postgresql://{user}:{password}@127.0.0.1:{pg_port}/{db}"
        ), path.name
        assert env["SEMANTIC_LAB_NEO4J_URI"] == (
            f"bolt://127.0.0.1:{env['SEMANTIC_LAB_NEO4J_BOLT_PORT']}"
        ), path.name
        assert env["SEMANTIC_LAB_CUBE_URL"] == (
            f"http://127.0.0.1:{env['SEMANTIC_LAB_CUBE_PORT']}"
        ), path.name


def test_no_port_is_shared() -> None:
    ports = [envfile.read(path)[key] for path in FILES.values() for key in PORT_KEYS]
    assert len(ports) == 8
    assert len(set(ports)) == 8
    assert not {"5433", "5434"} & set(ports)


def test_env_is_ignored_by_git() -> None:
    result = subprocess.run(
        ["git", "check-ignore", ".env"], cwd=ROOT, capture_output=True, check=False
    )
    assert result.returncode == 0
