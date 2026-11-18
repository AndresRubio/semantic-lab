import pytest

from semantic_lab.domain.errors import OntologyError
from semantic_lab.domain.ontology import (
    CONCEPT,
    NAMESPACE,
    XSD_TYPES,
    OntologyClass,
    Property,
    build_ontology,
)

STRING = next(t for t in XSD_TYPES if t.endswith("#string"))


def iri(name: str) -> str:
    return NAMESPACE + name


def cls(name: str, parent: str | None = None) -> OntologyClass:
    return OntologyClass(iri(name), iri(parent) if parent else None)


def obj(name: str, domain: str | None, range: str) -> Property:
    return Property(iri(name), "object", iri(domain) if domain else None, range)


def data(name: str, domain: str | None, range: str = STRING) -> Property:
    return Property(iri(name), "datatype", iri(domain) if domain else None, range)


CLASSES = [cls("B", "A"), cls("A")]
PROPERTIES = [obj("q", "A", iri("B")), obj("p", "B", CONCEPT), data("code", None)]

CASES = {
    "duplicate class": ([cls("A"), cls("A")], [], iri("A")),
    "class used as a property": (CLASSES, [obj("A", "A", iri("B"))], iri("A")),
    "property twice": (CLASSES, [data("n", "A"), data("n", "B")], iri("n")),
    "class outside the namespace": (
        [OntologyClass("https://other.example/X", None)],
        [],
        "https://other.example/X",
    ),
    "property outside the namespace": (
        CLASSES,
        [Property("https://other.example/p", "datatype", None, STRING)],
        "https://other.example/p",
    ),
    "parent is no class": ([cls("A", "Ghost")], [], iri("Ghost")),
    "subclass cycle": ([cls("A", "B"), cls("B", "A")], [], iri("A")),
    "object property without a domain": (CLASSES, [obj("p", None, iri("A"))], iri("p")),
    "object property domain is no class": (CLASSES, [obj("p", "Ghost", iri("A"))], iri("Ghost")),
    "object property range is neither class nor concept": (
        CLASSES,
        [obj("p", "A", iri("Ghost"))],
        iri("Ghost"),
    ),
    "datatype property range outside xsd": (
        CLASSES,
        [data("p", "A", "http://www.w3.org/2001/XMLSchema#boolean")],
        iri("p"),
    ),
    "datatype property domain is no class": (CLASSES, [data("p", "Ghost")], iri("Ghost")),
}


@pytest.mark.parametrize("case", CASES)
def test_build_refuses(case: str) -> None:
    classes, properties, named = CASES[case]
    with pytest.raises(OntologyError, match=named.replace(".", r"\.")):
        build_ontology(classes, properties)


def test_a_valid_pair_comes_back_sorted_by_iri() -> None:
    ontology = build_ontology(CLASSES, PROPERTIES)
    assert [c.iri for c in ontology.classes] == [iri("A"), iri("B")]
    assert [p.iri for p in ontology.properties] == [iri("code"), iri("p"), iri("q")]


def test_lookups_find_terms_and_refuse_unknown_ones() -> None:
    ontology = build_ontology(CLASSES, PROPERTIES)
    assert ontology.class_of(iri("B")).parent == iri("A")
    assert ontology.property_of(iri("p")).range == CONCEPT
    with pytest.raises(OntologyError, match="Ghost"):
        ontology.class_of(iri("Ghost"))
    with pytest.raises(OntologyError, match="ghost"):
        ontology.property_of(iri("ghost"))
