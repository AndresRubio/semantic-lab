import io
from pathlib import Path

import pytest

from semantic_lab.commands import smoke
from tests.support import envfile

STACK_ENV = Path(__file__).resolve().parent.parent / "stack.env"


@pytest.mark.db
def test_smoke_passes_on_the_stack(stack):
    out, err = io.StringIO(), io.StringIO()
    env = envfile.read(STACK_ENV)

    code = smoke.main(["--no-model"], env, out, err)

    assert code == 0, out.getvalue() + err.getvalue()
    lines = out.getvalue().splitlines()
    assert [line.split()[:2] for line in lines] == [
        ["ok", "postgres"],
        ["ok", "neo4j"],
        ["ok", "cube"],
    ]
