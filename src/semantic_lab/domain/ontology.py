from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from semantic_lab.domain.errors import OntologyError

NAMESPACE = "https://semantic-lab.example/ontology#"
# Taxonomy concepts have no class of their own: a property that points at one has this range.
CONCEPT = "http://www.w3.org/2004/02/skos/core#Concept"
XSD_TYPES = tuple(
    f"http://www.w3.org/2001/XMLSchema#{name}" for name in ("string", "integer", "decimal", "date")
)


@dataclass(frozen=True)
class OntologyClass:
    iri: str
    parent: str | None


@dataclass(frozen=True)
class Property:
    iri: str
    kind: Literal["object", "datatype"]
    domain: str | None
    range: str


@dataclass(frozen=True)
class Ontology:
    classes: tuple[OntologyClass, ...]
    properties: tuple[Property, ...]

    def class_of(self, iri: str) -> OntologyClass:
        for ontology_class in self.classes:
            if ontology_class.iri == iri:
                return ontology_class
        raise OntologyError(f"unknown class {iri}")

    def property_of(self, iri: str) -> Property:
        for prop in self.properties:
            if prop.iri == iri:
                return prop
        raise OntologyError(f"unknown property {iri}")


def build_ontology(
    classes: Iterable[OntologyClass], properties: Iterable[Property]
) -> Ontology:
    ordered_classes = tuple(sorted(classes, key=lambda c: c.iri))
    ordered_properties = tuple(sorted(properties, key=lambda p: p.iri))
    by_iri: dict[str, OntologyClass] = {}
    seen: set[str] = set()
    for term in (*(c.iri for c in ordered_classes), *(p.iri for p in ordered_properties)):
        if term in seen:
            raise OntologyError(f"term {term} is defined twice")
        if not term.startswith(NAMESPACE):
            raise OntologyError(f"term {term} is outside {NAMESPACE}")
        seen.add(term)
    for ontology_class in ordered_classes:
        by_iri[ontology_class.iri] = ontology_class
    for ontology_class in ordered_classes:
        if ontology_class.parent is not None and ontology_class.parent not in by_iri:
            raise OntologyError(
                f"class {ontology_class.iri} has parent {ontology_class.parent}, which is no class"
            )
    for ontology_class in ordered_classes:
        visited = {ontology_class.iri}
        current = ontology_class
        while current.parent is not None:
            current = by_iri[current.parent]
            if current.iri in visited:
                raise OntologyError(f"class {ontology_class.iri} is part of a cycle")
            visited.add(current.iri)
    for prop in ordered_properties:
        _check_property(prop, by_iri)
    return Ontology(classes=ordered_classes, properties=ordered_properties)


def _check_property(prop: Property, classes: dict[str, OntologyClass]) -> None:
    if prop.domain is not None and prop.domain not in classes:
        raise OntologyError(f"property {prop.iri} has domain {prop.domain}, which is no class")
    if prop.kind == "object":
        if prop.domain is None:
            raise OntologyError(f"object property {prop.iri} has no domain")
        if prop.range != CONCEPT and prop.range not in classes:
            raise OntologyError(
                f"object property {prop.iri} has range {prop.range}, which is neither a class "
                "nor skos:Concept"
            )
    elif prop.range not in XSD_TYPES:
        raise OntologyError(
            f"datatype property {prop.iri} has range {prop.range}, which is not one of the "
            "supported XSD types"
        )
