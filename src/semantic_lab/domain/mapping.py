from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from semantic_lab.domain.errors import MappingError, TaxonomyError
from semantic_lab.domain.ontology import XSD_TYPES, Ontology, Property
from semantic_lab.domain.records import DATA_TABLES, column_types
from semantic_lab.domain.taxonomy import Taxonomy


@dataclass(frozen=True)
class Condition:
    column: str
    under: tuple[str, ...]  # concept keys, sorted


@dataclass(frozen=True)
class ClassEntry:
    iri: str
    table: str
    key: tuple[str, ...]
    when: Condition | None


@dataclass(frozen=True)
class Link:
    table: str
    source: str  # `from` in the file
    target: str  # `to` in the file


@dataclass(frozen=True)
class PropertyEntry:
    iri: str
    columns: tuple[tuple[str, str], ...]  # (table, column); empty when `link` is set
    link: Link | None


@dataclass(frozen=True)
class Mapping:
    classes: tuple[ClassEntry, ...]
    properties: tuple[PropertyEntry, ...]

    def postgres_columns(self) -> frozenset[tuple[str, str]]:
        """Every (table, column) the mapping names, in a key, a condition, a property or a link."""
        found: set[tuple[str, str]] = set()
        for entry in self.classes:
            found.update((entry.table, column) for column in entry.key)
            if entry.when is not None:
                found.add((entry.table, entry.when.column))
        for prop in self.properties:
            found.update(prop.columns)
            if prop.link is not None:
                found.update(
                    (prop.link.table, column) for column in (prop.link.source, prop.link.target)
                )
        return frozenset(found)


def build_mapping(
    classes: Iterable[ClassEntry], properties: Iterable[PropertyEntry]
) -> Mapping:
    ordered_classes = tuple(sorted(classes, key=lambda c: c.iri))
    ordered_properties = tuple(sorted(properties, key=lambda p: p.iri))
    for section in (ordered_classes, ordered_properties):
        iris = [entry.iri for entry in section]
        for iri in sorted({i for i in iris if iris.count(i) > 1}):
            raise MappingError(f"term {iri} has two entries")
    return Mapping(classes=ordered_classes, properties=ordered_properties)


ALL_TABLES = tuple(name for name, _ in DATA_TABLES)
# What a column must hold for a datatype property of each range. The fit is exact: an int column
# under xsd:decimal is refused, so the datatype of an exported literal is always the column's.
RANGE_TYPES: dict[str, type[Any]] = dict(zip(XSD_TYPES, (str, int, Decimal, date), strict=True))


def _fields(table: str) -> dict[str, type[Any]] | None:
    """The columns of a data table with what each holds, or None when the name is no data table."""
    try:
        return column_types(table)
    except KeyError:
        return None


def problems(
    mapping: Mapping,
    ontology: Ontology,
    taxonomy: Taxonomy,
    tables: tuple[str, ...] = ALL_TABLES,
) -> tuple[str, ...]:
    """One line per fault, sorted. `tables` are the data tables whose columns must all be mapped."""
    found = [
        *_term_problems(mapping, ontology),
        *_class_problems(mapping, taxonomy),
        *_hierarchy_problems(mapping, ontology),
        *_property_problems(mapping, ontology),
        *_coverage_problems(mapping, tables),
    ]
    return tuple(sorted(found))


def _term_problems(mapping: Mapping, ontology: Ontology) -> list[str]:
    class_iris = {c.iri for c in ontology.classes}
    property_iris = {p.iri for p in ontology.properties}
    entered_classes = {e.iri for e in mapping.classes}
    entered_properties = {e.iri for e in mapping.properties}
    lines = [f"class {iri} has no entry" for iri in sorted(class_iris - entered_classes)]
    lines += [f"property {iri} has no entry" for iri in sorted(property_iris - entered_properties)]
    for iri in sorted(entered_classes - class_iris):
        held = "a property" if iri in property_iris else "no term"
        lines.append(f"class entry {iri}: the ontology holds it as {held}")
    for iri in sorted(entered_properties - property_iris):
        held = "a class" if iri in class_iris else "no term"
        lines.append(f"property entry {iri}: the ontology holds it as {held}")
    return lines


def _class_problems(mapping: Mapping, taxonomy: Taxonomy) -> list[str]:
    lines: list[str] = []
    for entry in mapping.classes:
        fields = _fields(entry.table)
        if fields is None:
            lines.append(f"class {entry.iri}: table {entry.table} is no data table")
            continue
        named = list(entry.key)
        if entry.when is not None:
            named.append(entry.when.column)
            for key in entry.when.under:
                try:
                    taxonomy.get(key)
                except TaxonomyError:
                    lines.append(f"class {entry.iri}: concept key {key} is not in the taxonomy")
        lines += [
            f"class {entry.iri}: {column} is not a column of {entry.table}"
            for column in named
            if column not in fields
        ]
    return lines


def _hierarchy_problems(mapping: Mapping, ontology: Ontology) -> list[str]:
    lines: list[str] = []
    unconditional: dict[str, list[str]] = defaultdict(list)
    for entry in mapping.classes:
        if entry.when is None:
            unconditional[entry.table].append(entry.iri)
    for table, iris in sorted(unconditional.items()):
        if len(iris) > 1:
            lines.append(
                f"table {table} has {len(iris)} unconditional class entries: "
                f"{', '.join(sorted(iris))}"
            )
    known = {c.iri: c for c in ontology.classes}
    for entry in mapping.classes:
        if entry.when is None or entry.iri not in known:
            continue
        parent = known[entry.iri].parent
        if parent is None:
            lines.append(f"class {entry.iri} is conditional but has no parent in the ontology")
        elif not any(
            e.iri == parent and e.when is None and (e.table, e.key) == (entry.table, entry.key)
            for e in mapping.classes
        ):
            lines.append(
                f"class {entry.iri} is conditional, and its parent {parent} has no "
                f"unconditional entry on table {entry.table} with key {list(entry.key)}"
            )
    return lines


def _property_problems(mapping: Mapping, ontology: Ontology) -> list[str]:
    lines: list[str] = []
    entered = {e.table for e in mapping.classes}
    base = {e.table: e.iri for e in mapping.classes if e.when is None}
    domains = _domains(mapping, ontology)
    terms = {p.iri: p for p in ontology.properties}
    for prop in mapping.properties:
        term = terms.get(prop.iri)
        for table, column in prop.columns:
            if table not in base:
                lines.append(
                    f"property {prop.iri}: column {table}.{column} is on a table with no "
                    "unconditional class entry"
                )
            fields = _fields(table)
            if fields is None:
                continue
            if column not in fields:
                lines.append(f"property {prop.iri}: {column} is not a column of {table}")
            elif term is not None:
                lines += _fit_problems(term, table, column, fields[column], base, domains)
        link = prop.link
        if link is None:
            continue
        if term is not None and term.kind == "datatype":
            lines.append(f"property {prop.iri} is a datatype property and cannot be a link")
        if link.table in entered:
            lines.append(f"property {prop.iri}: link table {link.table} has a class entry")
        fields = _fields(link.table)
        if fields is None:
            lines.append(f"property {prop.iri}: link table {link.table} is no data table")
            continue
        for column in (link.source, link.target):
            if column not in fields:
                lines.append(f"property {prop.iri}: {column} is not a column of {link.table}")
            elif fields[column] is not str:
                lines.append(_reference_problem(prop.iri, link.table, column, fields[column]))
    return lines


def _domains(mapping: Mapping, ontology: Ontology) -> dict[str, set[str]]:
    """For each table, the classes a property on it may have as its domain: the classes
    entered on the table and the classes above them."""
    parents = {c.iri: c.parent for c in ontology.classes}
    found: dict[str, set[str]] = defaultdict(set)
    for entry in mapping.classes:
        iri: str | None = entry.iri
        while iri is not None and iri not in found[entry.table]:
            found[entry.table].add(iri)
            iri = parents.get(iri)
    return found


def _fit_problems(
    term: Property,
    table: str,
    column: str,
    held: type[Any],
    base: dict[str, str],
    domains: dict[str, set[str]],
) -> list[str]:
    """The problems of a column under a property: a table outside the domain, a type the range
    does not take."""
    lines: list[str] = []
    if term.domain is not None and table in base and term.domain not in domains[table]:
        lines.append(
            f"property {term.iri}: column {table}.{column} is on the table of {base[table]}, "
            f"and its domain is {term.domain}"
        )
    if term.kind == "object":
        if held is not str:
            lines.append(_reference_problem(term.iri, table, column, held))
        return lines
    needed = RANGE_TYPES.get(term.range)
    if needed is not None and held is not needed:
        lines.append(
            f"property {term.iri}: column {table}.{column} holds {held.__name__}, and its range "
            f"{term.range} needs {needed.__name__}"
        )
    return lines


def _reference_problem(iri: str, table: str, column: str, held: type[Any]) -> str:
    return f"property {iri}: column {table}.{column} holds {held.__name__}, and a reference needs str"


def _coverage_problems(mapping: Mapping, tables: tuple[str, ...]) -> list[str]:
    lines: list[str] = []
    owners: dict[tuple[str, str], list[str]] = defaultdict(list)
    for prop in mapping.properties:
        for pair in prop.columns:
            owners[pair].append(prop.iri)
        if prop.link is not None:
            for name in (prop.link.source, prop.link.target):
                owners[(prop.link.table, name)].append(prop.iri)
    used = {e.table for e in mapping.classes} | {
        p.link.table for p in mapping.properties if p.link is not None
    }
    for table in tables:
        fields = _fields(table)
        if fields is None:
            continue
        if table not in used:
            lines.append(f"table {table} is neither a class's table nor a link's")
            continue
        for column in sorted(fields):
            who = owners.get((table, column), [])
            if not who:
                lines.append(f"column {table}.{column} is mapped by no property")
            elif len(who) > 1:
                lines.append(
                    f"column {table}.{column} is mapped by {len(who)} properties: "
                    f"{', '.join(sorted(who))}"
                )
    return lines
