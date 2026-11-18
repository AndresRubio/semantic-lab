from collections.abc import Collection
from pathlib import Path
from typing import Any

import yaml

from semantic_lab.domain.errors import MappingError
from semantic_lab.domain.mapping import (
    ClassEntry,
    Condition,
    Link,
    Mapping,
    PropertyEntry,
    build_mapping,
)
from semantic_lab.domain.ontology import NAMESPACE

PREFIX = "sl:"


class _UniqueKeys(yaml.SafeLoader):
    """A safe loader that refuses the same key twice in one mapping. PyYAML keeps the last one."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen: set[tuple[str, str]] = set()
        for key, _ in node.value:
            if not isinstance(key, yaml.ScalarNode):
                continue
            if (key.tag, key.value) in seen:
                raise MappingError(
                    f"the key {key.value!r} appears twice, on line {key.start_mark.line + 1}"
                )
            seen.add((key.tag, key.value))
        return super().construct_mapping(node, deep)


def load_mapping(file: Path) -> Mapping:
    """Read the mapping file. Any fault is a one-line MappingError that starts with its name."""
    name = file.name
    try:
        text = file.read_text(encoding="utf-8")
    except OSError as error:
        raise MappingError(f"{name}: cannot be read: {error.strerror or error}") from error
    except UnicodeDecodeError as error:
        raise MappingError(f"{name}: is not UTF-8") from error
    try:
        return _mapping(yaml.load(text, Loader=_UniqueKeys))
    except yaml.YAMLError as error:
        raise MappingError(f"{name}: is not YAML: {' '.join(str(error).split())}") from error
    except MappingError as error:
        raise MappingError(f"{name}: {error}") from None


def _mapping(document: Any) -> Mapping:
    if not isinstance(document, dict):
        raise MappingError("the top level must be a mapping with the keys classes and properties")
    _keys(document, "the top level", ["classes", "properties"])
    classes = [_class(*item) for item in _entries(document["classes"], "classes")]
    properties = [_property(*item) for item in _entries(document["properties"], "properties")]
    return build_mapping(classes, properties)


def _entries(section: Any, name: str) -> list[tuple[str, Any]]:
    if not isinstance(section, dict):
        raise MappingError(f"{name} must be a mapping from a term to its entry")
    for term in section:
        if not isinstance(term, str) or not term.startswith(PREFIX) or term == PREFIX:
            raise MappingError(f"term {term!r} does not start with {PREFIX}")
    return list(section.items())


def _iri(term: str) -> str:
    return NAMESPACE + term[len(PREFIX) :]


def _keys(
    value: Any, where: str, required: Collection[str], optional: Collection[str] = ()
) -> dict[str, Any]:
    """The value as a dict that holds every required key and no key beyond the allowed ones."""
    if not isinstance(value, dict):
        raise MappingError(f"{where} must be a mapping")
    for key in value:
        if key not in (*required, *optional):
            raise MappingError(f"{where} has the unknown key {key!r}")
    for key in required:
        if key not in value:
            raise MappingError(f"{where} has no {key}")
    return value


def _names(value: Any, where: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise MappingError(f"{where} must be a non-empty list of strings")
    return tuple(value)


def _name(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise MappingError(f"{where} must be a non-empty string")
    return value


def _class(term: str, entry: Any) -> ClassEntry:
    entry = _keys(entry, f"class {term}", ["postgres"])
    where = f"class {term}: postgres"
    postgres = _keys(entry["postgres"], where, ["table", "key"], ["when"])
    when = None
    if "when" in postgres:
        condition = _keys(postgres["when"], f"{where}.when", ["column", "under"])
        when = Condition(
            _name(condition["column"], f"{where}.when.column"),
            tuple(sorted(_names(condition["under"], f"{where}.when.under"))),
        )
    return ClassEntry(
        _iri(term),
        _name(postgres["table"], f"{where}.table"),
        _names(postgres["key"], f"{where}.key"),
        when,
    )


def _column(value: str, where: str) -> tuple[str, str]:
    table, dot, column = value.partition(".")
    if not dot or not table or not column or "." in column:
        raise MappingError(f"{where}: {value!r} is not of the form table.column")
    return table, column


def _property(term: str, entry: Any) -> PropertyEntry:
    where = f"property {term}"
    entry = _keys(entry, where, ["postgres"])
    where = f"{where}: postgres"
    postgres = _keys(entry["postgres"], where, [], ["columns", "link"])
    if ("columns" in postgres) == ("link" in postgres):
        raise MappingError(f"{where} must have exactly one of columns and link")
    if "columns" in postgres:
        names = _names(postgres["columns"], f"{where}.columns")
        return PropertyEntry(_iri(term), tuple(_column(n, f"{where}.columns") for n in names), None)
    link = _keys(postgres["link"], f"{where}.link", ["table", "from", "to"])
    return PropertyEntry(
        _iri(term),
        (),
        Link(
            _name(link["table"], f"{where}.link.table"),
            _name(link["from"], f"{where}.link.from"),
            _name(link["to"], f"{where}.link.to"),
        ),
    )
