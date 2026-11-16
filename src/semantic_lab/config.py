"""The lab's settings. Every value comes from the environment; none has a default."""

from collections.abc import Mapping
from dataclasses import dataclass, field


class MissingSetting(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"{name} is missing or empty")
        self.name = name


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str = field(repr=False)
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str = field(repr=False)
    cube_url: str
    cube_secret: str = field(repr=False)
    ollama_url: str
    model: str


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "")
    if not value:
        raise MissingSetting(name)
    return value


def load(env: Mapping[str, str]) -> Settings:
    return Settings(
        postgres_dsn=_required(env, "SEMANTIC_LAB_POSTGRES_DSN"),
        neo4j_uri=_required(env, "SEMANTIC_LAB_NEO4J_URI"),
        neo4j_user=_required(env, "SEMANTIC_LAB_NEO4J_USER"),
        neo4j_password=_required(env, "SEMANTIC_LAB_NEO4J_PASSWORD"),
        cube_url=_required(env, "SEMANTIC_LAB_CUBE_URL"),
        cube_secret=_required(env, "SEMANTIC_LAB_CUBE_SECRET"),
        ollama_url=_required(env, "SEMANTIC_LAB_OLLAMA_URL"),
        model=_required(env, "SEMANTIC_LAB_MODEL"),
    )
