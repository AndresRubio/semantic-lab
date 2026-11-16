import io

import pytest

from semantic_lab.commands import smoke


@pytest.mark.db
def test_smoke_passes_on_the_stack(stack):
    out, err = io.StringIO(), io.StringIO()
    env = {
        "SEMANTIC_LAB_POSTGRES_DSN": stack.postgres_dsn,
        "SEMANTIC_LAB_NEO4J_URI": stack.neo4j_uri,
        "SEMANTIC_LAB_NEO4J_USER": stack.neo4j_user,
        "SEMANTIC_LAB_NEO4J_PASSWORD": stack.neo4j_password,
        "SEMANTIC_LAB_CUBE_URL": stack.cube_url,
        "SEMANTIC_LAB_CUBE_SECRET": stack.cube_secret,
        "SEMANTIC_LAB_OLLAMA_URL": stack.ollama_url,
        "SEMANTIC_LAB_MODEL": stack.model,
    }

    code = smoke.main(["--no-model"], env, out, err)

    assert code == 0, out.getvalue() + err.getvalue()
    lines = out.getvalue().splitlines()
    assert [line.split()[:2] for line in lines] == [
        ["ok", "postgres"],
        ["ok", "neo4j"],
        ["ok", "cube"],
    ]
