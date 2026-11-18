import re
from collections.abc import Callable
from dataclasses import dataclass
from operator import attrgetter
from typing import Any
from urllib.parse import quote

from rdflib import RDF, Graph, Literal, URIRef

from semantic_lab.domain.errors import MappingError
from semantic_lab.domain.mapping import ClassEntry, Mapping
from semantic_lab.domain.ontology import CONCEPT, NAMESPACE, Ontology
from semantic_lab.domain.records import Dataset, rows
from semantic_lab.domain.taxonomy import Taxonomy

DATA = "https://semantic-lab.example/data/"
XSD_STRING = "http://www.w3.org/2001/XMLSchema#string"

Value = Callable[[Any], URIRef | Literal | None]


@dataclass(frozen=True)
class _Class:
    """The unconditional class of a table: what its node IRIs are made of."""

    iri: str
    table: str
    slug: str
    key: tuple[str, ...]


def export(dataset: Dataset, taxonomy: Taxonomy, ontology: Ontology, mapping: Mapping) -> Graph:
    """Every row of the dataset as RDF, following the mapping. Lookups are built once."""
    concepts = {c.key: c.iri for c in taxonomy.concepts}
    base = _base_classes(mapping)
    by_iri = {entry.iri: entry for entry in mapping.classes}
    types = _types(mapping, taxonomy)
    graph = Graph()
    graph.bind("sl", NAMESPACE)
    objects = _reference_builders(ontology, mapping, base, by_iri, taxonomy, concepts)
    for table, entry in base.items():
        columns = objects.columns.get(table, ())
        node_of = _node_builder(entry)
        for row in rows(dataset, table):
            node = node_of(row)
            for rdf_type in types.get(table, ()):
                if rdf_type.when(row):
                    graph.add((node, RDF.type, rdf_type.iri))
            for getter, predicate, value_of in columns:
                value = value_of(getter(row))
                if value is not None:
                    graph.add((node, predicate, value))
    for link in objects.links:
        for row in rows(dataset, link.table):
            graph.add((link.subject(row), link.predicate, link.target(row)))
    return graph


@dataclass(frozen=True)
class _Type:
    iri: URIRef
    when: Callable[[Any], bool]


def _types(mapping: Mapping, taxonomy: Taxonomy) -> dict[str, list[_Type]]:
    found: dict[str, list[_Type]] = {}
    for entry in mapping.classes:
        found.setdefault(entry.table, []).append(_Type(URIRef(entry.iri), _holds(entry, taxonomy)))
    return found


def _holds(entry: ClassEntry, taxonomy: Taxonomy) -> Callable[[Any], bool]:
    condition = entry.when
    if condition is None:
        return lambda row: True
    keys = set(condition.under)
    for key in condition.under:
        keys.update(c.key for c in taxonomy.descendants(key))
    column = attrgetter(condition.column)
    return lambda row: column(row) in keys


def _base_classes(mapping: Mapping) -> dict[str, _Class]:
    return {
        entry.table: _Class(entry.iri, entry.table, _slug(entry.iri), entry.key)
        for entry in mapping.classes
        if entry.when is None
    }


def _slug(iri: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "-", iri.removeprefix(NAMESPACE)).lower()


def _node_builder(entry: _Class) -> Callable[[Any], URIRef]:
    prefix = f"{DATA}{entry.slug}/"
    getters = tuple(attrgetter(column) for column in entry.key)
    return lambda row: URIRef(prefix + "/".join(quote(str(g(row)), safe="") for g in getters))


@dataclass(frozen=True)
class _Link:
    table: str
    predicate: URIRef
    subject: Callable[[Any], URIRef]
    target: Callable[[Any], URIRef]


@dataclass(frozen=True)
class _Builders:
    columns: dict[str, list[tuple[Callable[[Any], Any], URIRef, Value]]]
    links: list[_Link]


def _reference_builders(
    ontology: Ontology,
    mapping: Mapping,
    base: dict[str, _Class],
    by_iri: dict[str, ClassEntry],
    taxonomy: Taxonomy,
    concepts: dict[str, str],
) -> _Builders:
    def concept(key: str) -> URIRef:
        iri = concepts.get(key)
        return URIRef(iri if iri is not None else taxonomy.get(key).iri)

    def class_of(iri: str, why: str) -> _Class:
        entry = by_iri.get(iri)
        if entry is None or entry.table not in base:
            raise MappingError(f"{why}: class {iri} has no unconditional entry")
        target = base[entry.table]
        if len(target.key) != 1:
            raise MappingError(
                f"{why}: class {iri} has a key of {len(target.key)} columns, not one"
            )
        return target

    def reference(range_iri: str, why: str) -> Callable[[Any], URIRef]:
        if range_iri == CONCEPT:
            return lambda value: concept(value)
        prefix = f"{DATA}{class_of(range_iri, why).slug}/"
        return lambda value: URIRef(prefix + quote(str(value), safe=""))

    columns: dict[str, list[tuple[Callable[[Any], Any], URIRef, Value]]] = {}
    links: list[_Link] = []
    for entry in mapping.properties:
        prop = ontology.property_of(entry.iri)
        predicate = URIRef(prop.iri)
        why = f"property {prop.iri}"
        if entry.link is not None:
            if prop.domain is None:
                raise MappingError(f"{why}: a link needs a domain")
            links.append(
                _Link(
                    entry.link.table,
                    predicate,
                    _through(attrgetter(entry.link.source), reference(prop.domain, why)),
                    _through(attrgetter(entry.link.target), reference(prop.range, why)),
                )
            )
            continue
        if prop.kind == "object":
            value_of = _skip_null(reference(prop.range, why))
        else:
            value_of = _skip_null(_literal(prop.range))
        for table, column in entry.columns:
            columns.setdefault(table, []).append((attrgetter(column), predicate, value_of))
    return _Builders(columns, links)


def _through(get: Callable[[Any], Any], build: Callable[[Any], URIRef]) -> Callable[[Any], URIRef]:
    def apply(row: Any) -> URIRef:
        return build(get(row))

    return apply


def _skip_null(build: Callable[[Any], URIRef | Literal]) -> Value:
    def apply(value: Any) -> URIRef | Literal | None:
        return None if value is None else build(value)

    return apply


def _literal(range_iri: str) -> Callable[[Any], Literal]:
    """The datatype comes from the property's range, so a column of the wrong type shows."""
    if range_iri == XSD_STRING:
        return Literal
    datatype = URIRef(range_iri)

    def build(value: Any) -> Literal:
        return Literal(value, datatype=datatype)

    return build
