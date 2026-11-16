from pathlib import Path

import pytest

from semantic_lab import config
from tests.support import envfile

ROOT = Path(__file__).resolve().parent.parent


def test_load_reads_the_eight_settings() -> None:
    settings = config.load(envfile.read(ROOT / ".env.example"))
    assert settings.postgres_dsn == "postgresql://lab:lab-local-postgres@127.0.0.1:5440/lab"
    assert settings.neo4j_uri == "bolt://127.0.0.1:7687"
    assert settings.neo4j_user == "neo4j"
    assert settings.neo4j_password == "lab-local-graph"
    assert settings.cube_url == "http://127.0.0.1:4000"
    assert settings.cube_secret == "lab-local-cube-secret"
    assert settings.ollama_url == "http://127.0.0.1:11434"
    assert settings.model == "qwen2.5-coder:7b"


@pytest.mark.parametrize(
    "name",
    [
        "SEMANTIC_LAB_POSTGRES_DSN",
        "SEMANTIC_LAB_NEO4J_URI",
        "SEMANTIC_LAB_NEO4J_USER",
        "SEMANTIC_LAB_NEO4J_PASSWORD",
        "SEMANTIC_LAB_CUBE_URL",
        "SEMANTIC_LAB_CUBE_SECRET",
        "SEMANTIC_LAB_OLLAMA_URL",
        "SEMANTIC_LAB_MODEL",
    ],
)
def test_a_missing_or_empty_setting_is_named(name: str) -> None:
    env = envfile.read(ROOT / ".env.example")
    for broken in ({k: v for k, v in env.items() if k != name}, {**env, name: ""}):
        with pytest.raises(config.MissingSetting) as caught:
            config.load(broken)
        assert caught.value.name == name
