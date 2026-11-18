from collections import Counter
from pathlib import Path

import pytest

from semantic_lab.domain.errors import OntologyError
from semantic_lab.domain.ontology import CONCEPT, NAMESPACE as SL, Ontology
from semantic_lab.rdf.ontology import ontology_graph, ontology_of

XSD = "http://www.w3.org/2001/XMLSchema#"
HEAD = f"""@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <{XSD}> .
@prefix sl: <{SL}> .
sl:A a owl:Class . sl:B a owl:Class . sl:C a owl:Class .
"""
FAULTS = {
    "two subclassOf": ("sl:C", "sl:C rdfs:subClassOf sl:A, sl:B ."),
    "two domains": (
        "sl:p",
        "sl:p a owl:ObjectProperty ; rdfs:domain sl:A, sl:B ; rdfs:range sl:C .",
    ),
    "no range": ("sl:p", "sl:p a owl:DatatypeProperty ; rdfs:domain sl:A ."),
    "two ranges": (
        "sl:p",
        "sl:p a owl:DatatypeProperty ; rdfs:domain sl:A ; rdfs:range xsd:string, xsd:date .",
    ),
}


def load(tmp_path: Path, text: str) -> Ontology:
    file = tmp_path / "o.ttl"
    file.write_text(HEAD + text)
    return ontology_of(ontology_graph(file))


@pytest.mark.parametrize("case", FAULTS)
def test_a_broken_term_is_refused(case: str, tmp_path: Path) -> None:
    named, text = FAULTS[case]
    with pytest.raises(OntologyError, match=named.replace("sl:", SL).replace(".", r"\.")):
        load(tmp_path, text)


def test_a_good_file_loads(tmp_path: Path) -> None:
    ontology = load(
        tmp_path,
        "sl:B rdfs:subClassOf sl:A . "
        "sl:p a owl:ObjectProperty ; rdfs:domain sl:B ; rdfs:range sl:A . "
        "sl:n a owl:DatatypeProperty ; rdfs:range xsd:string .",
    )
    assert [(c.iri, c.parent) for c in ontology.classes] == [
        (SL + "A", None),
        (SL + "B", SL + "A"),
        (SL + "C", None),
    ]
    assert [(p.iri, p.kind, p.domain) for p in ontology.properties] == [
        (SL + "n", "datatype", None),
        (SL + "p", "object", SL + "B"),
    ]


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(OntologyError, match=r"nope\.ttl"):
        ontology_graph(tmp_path / "nope.ttl")


def test_the_file_holds_14_classes_and_50_properties(ontology: Ontology) -> None:
    assert len(ontology.classes) == 14
    assert Counter(p.kind for p in ontology.properties) == {"object": 18, "datatype": 32}


def test_the_two_subclasses(ontology: Ontology) -> None:
    parents = {c.iri: c.parent for c in ontology.classes if c.parent}
    assert parents == {SL + "Blend": SL + "Product", SL + "SingleLotProduct": SL + "Product"}


def test_only_code_and_name_have_no_domain(ontology: Ontology) -> None:
    assert {p.iri for p in ontology.properties if p.domain is None} == {SL + "code", SL + "name"}


def test_pinned_terms(ontology: Ontology) -> None:
    share = ontology.property_of(SL + "share")
    assert (share.kind, share.domain, share.range) == (
        "datatype",
        SL + "BatchComponent",
        XSD + "decimal",
    )
    region = ontology.property_of(SL + "inRegion")
    assert (region.domain, region.range) == (SL + "Cooperative", CONCEPT)
