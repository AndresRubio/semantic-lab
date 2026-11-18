from pathlib import Path

import pytest

from semantic_lab.domain.errors import MappingError, OntologyError
from semantic_lab.rdf import turtle

PREFIX = "@prefix ex: <https://semantic-lab.example/x#> .\n"


def test_two_files_become_one_graph(tmp_path: Path) -> None:
    first = tmp_path / "a.ttl"
    second = tmp_path / "b.ttl"
    first.write_text(PREFIX + "ex:a ex:p ex:b .\n", encoding="utf-8")
    second.write_text(PREFIX + "ex:c ex:p ex:d .\nex:e ex:p ex:f .\n", encoding="utf-8")
    assert len(turtle.read([first], OntologyError)) == 1
    assert len(turtle.read([first, second], OntologyError)) == 3


def test_a_broken_file_raises_the_given_error(tmp_path: Path) -> None:
    broken = tmp_path / "broken.ttl"
    broken.write_text(PREFIX + "ex:a ex:p\n\nex:b .. .\n", encoding="utf-8")
    with pytest.raises(OntologyError, match=r"broken\.ttl: not valid Turtle") as refused:
        turtle.read([broken], OntologyError)
    assert "\n" not in str(refused.value) and str(tmp_path) not in str(refused.value)


def test_a_missing_file_raises_the_given_error(tmp_path: Path) -> None:
    with pytest.raises(MappingError, match=r"absent\.ttl") as refused:
        turtle.read([tmp_path / "absent.ttl"], MappingError)
    assert str(tmp_path) not in str(refused.value)
