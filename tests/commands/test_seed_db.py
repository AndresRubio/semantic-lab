import io
from pathlib import Path

import pytest

from semantic_lab.commands import seed
from semantic_lab.seed import load
from tests.support import envfile

STACK_ENV = Path(__file__).resolve().parent.parent / "stack.env"


def run_seed() -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = seed.main([], envfile.read(STACK_ENV), out, err)
    return code, out.getvalue(), err.getvalue()


@pytest.mark.db
def test_seed_prints_17_lines_and_fills_the_tables(stack):
    code, out, err = run_seed()

    assert code == 0, err
    lines = out.splitlines()
    assert [line.split()[0] for line in lines] == list(load.TABLES)
    assert len(lines) == 17
    assert "order_line  60000" in lines


@pytest.mark.db
def test_seed_twice_gives_the_same_output(stack):
    first = run_seed()
    second = run_seed()

    assert first[0] == second[0] == 0
    assert first[1] == second[1]
