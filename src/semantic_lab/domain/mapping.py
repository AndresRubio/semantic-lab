import dataclasses
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from semantic_lab.domain.errors import MappingError, TaxonomyError
from semantic_lab.domain.ontology import Ontology
from semantic_lab.domain.records import DATA_TABLES, record_type
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


def _fields(table: str) -> frozenset[str] | None:
    """The columns of a data table, or None when the name is no data table."""
    try:
        return frozenset(f.name for f in dataclasses.fields(record_type(table)))
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
        columns = list(entry.key)
        if entry.when is not None:
            columns.append(entry.when.column)
            for key in entry.when.under:
                try:
                    taxonomy.get(key)
                except TaxonomyError:
                    lines.append(f"class {entry.iri}: concept key {key} is not in the taxonomy")
        lines += [
            f"class {entry.iri}: {column} is not a column of {entry.table}"
            for column in columns
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
    unconditional = {e.table for e in mapping.classes if e.when is None}
    kinds = {p.iri: p.kind for p in ontology.properties}
    for prop in mapping.properties:
        for table, column in prop.columns:
            if table not in unconditional:
                lines.append(
                    f"property {prop.iri}: column {table}.{column} is on a table with no "
                    "unconditional class entry"
                )
            fields = _fields(table)
            if fields is not None and column not in fields:
                lines.append(f"property {prop.iri}: {column} is not a column of {table}")
        link = prop.link
        if link is None:
            continue
        if kinds.get(prop.iri) == "datatype":
            lines.append(f"property {prop.iri} is a datatype property and cannot be a link")
        if link.table in entered:
            lines.append(f"property {prop.iri}: link table {link.table} has a class entry")
        fields = _fields(link.table)
        if fields is None:
            lines.append(f"property {prop.iri}: link table {link.table} is no data table")
            continue
        lines += [
            f"property {prop.iri}: {column} is not a column of {link.table}"
            for column in (link.source, link.target)
            if column not in fields
        ]
    return lines


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
