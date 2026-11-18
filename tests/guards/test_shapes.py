from dataclasses import dataclass

import pytest
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import SH

from semantic_lab.domain.mapping import Mapping
from semantic_lab.domain.ontology import Ontology
from semantic_lab.domain.records import Dataset
from semantic_lab.domain.sample import first_orders
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.rdf.ontology import ontology_graph
from semantic_lab.rdf.shacl import validate
from semantic_lab.rdf.taxonomy import taxonomy_graph
from tests.conftest import ONTOLOGY_FILE, TAXONOMY_DIRECTORY
from tests.support import data_faults
from tests.support.data_faults import CHANGES, KINDS, data_graph

TAXONOMY = "https://semantic-lab.example/taxonomy/"
SL = "https://semantic-lab.example/ontology#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
PREFIXES = f"""@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <{RDFS}> .
@prefix skos: <{SKOS}> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix t: <{TAXONOMY}t#> .
@prefix sl: <{SL}> .
"""
LABELS = '"{0}"@en, "{0}"@es'


def concept(name: str, extra: str = "", scheme: str = "t") -> str:
    return (
        f't:{name} a skos:Concept ; skos:notation "t.{name}" ;'
        f" skos:prefLabel {LABELS.format(name)} ; {extra} skos:inScheme <{TAXONOMY}{scheme}> ."
    )


def scheme(name: str) -> str:
    return (
        f'<{TAXONOMY}{name}> a skos:ConceptScheme ; skos:notation "{name}" ;'
        f" skos:prefLabel {LABELS.format(name)} ."
    )


def term(name: str, kind: str, body: str) -> str:
    return (
        f"sl:{name} a owl:{kind} ; {body} rdfs:label {LABELS.format(name)} ;"
        f' rdfs:comment "{name}"@en .'
    )


# A conforming graph as named lines. A fault replaces some lines and adds some text, so the
# faulty graph differs from the conforming one by that change alone.
TAXONOMY_LINES = {
    "scheme t": scheme("t"),
    "scheme u": scheme("u"),
    "a": concept("a"),
    "b": concept("b", "skos:broader t:a ;"),
    "c": concept("c", "skos:broader t:b ;"),
}
ONTOLOGY_LINES = {
    "Owner": term("Owner", "Class", ""),
    "Other": term("Other", "Class", ""),
    "C": term("C", "Class", "rdfs:subClassOf sl:Owner ;"),
    "op": term("op", "ObjectProperty", "rdfs:domain sl:Owner ; rdfs:range sl:C ;"),
    "cp": term("cp", "ObjectProperty", "rdfs:domain sl:Owner ; rdfs:range skos:Concept ;"),
    "dp": term("dp", "DatatypeProperty", "rdfs:domain sl:Owner ; rdfs:range xsd:string ;"),
    "dq": term("dq", "DatatypeProperty", "rdfs:range xsd:date ;"),
}


@dataclass(frozen=True)
class Fault:
    focus: str
    constraint: str
    path: str | None = None
    replace: tuple[tuple[str, str], ...] = ()
    add: str = ""


def graph_of(lines: dict[str, str], fault: Fault | None = None) -> Graph:
    chosen = dict(lines)
    text = ""
    if fault is not None:
        for name, new in fault.replace:
            assert new != chosen[name], f"{name} did not change"
            chosen[name] = new
        text = fault.add
    return Graph().parse(data=PREFIXES + "\n".join(chosen.values()) + "\n" + text, format="turtle")


T_NOTATION = SKOS + "notation"
T_LABEL = SKOS + "prefLabel"
O_LABEL = RDFS + "label"
O_COMMENT = RDFS + "comment"
O_DOMAIN = RDFS + "domain"
O_RANGE = RDFS + "range"


def at(name: str) -> str:
    return f"{TAXONOMY}t#{name}"


def tax(name: str, old: str, new: str) -> tuple[tuple[str, str], ...]:
    return ((name, TAXONOMY_LINES[name].replace(old, new)),)


def onto(name: str, old: str, new: str) -> tuple[tuple[str, str], ...]:
    return ((name, ONTOLOGY_LINES[name].replace(old, new)),)


TAXONOMY_FAULTS = {
    "a node with skos:inScheme and no type": Fault(
        at("d"), "ClassConstraintComponent", add=f"t:d skos:inScheme <{TAXONOMY}t> ."
    ),
    "notation t.a on the IRI of b": Fault(
        at("b"), "SPARQLConstraintComponent", None, tax("b", '"t.b"', '"t.a"')
    ),
    "two English prefLabels": Fault(
        at("a"), "UniqueLangConstraintComponent", T_LABEL, tax("a", '"a"@es', '"aa"@en')
    ),
    "a prefLabel in French": Fault(
        at("a"), "LanguageInConstraintComponent", T_LABEL, tax("a", '"a"@es', '"a"@fr')
    ),
    "an altLabel in French": Fault(
        at("a"),
        "LanguageInConstraintComponent",
        SKOS + "altLabel",
        add='t:a skos:altLabel "a"@fr .',
    ),
    "a third prefLabel": Fault(
        at("a"), "MaxCountConstraintComponent", T_LABEL, add='t:a skos:prefLabel "a"@en-GB .'
    ),
    "one prefLabel only": Fault(
        at("a"), "MinCountConstraintComponent", T_LABEL, tax("a", ', "a"@es', "")
    ),
    "no notation": Fault(
        at("a"), "MinCountConstraintComponent", T_NOTATION, tax("a", ' skos:notation "t.a" ;', "")
    ),
    "two notations": Fault(
        at("a"),
        "MaxCountConstraintComponent",
        T_NOTATION,
        add='t:a skos:notation "t.a"^^xsd:token .',
    ),
    "no scheme": Fault(
        at("d"),
        "MinCountConstraintComponent",
        SKOS + "inScheme",
        add=f't:d a skos:Concept ; skos:notation "t.d" ; skos:prefLabel {LABELS.format("d")} .',
    ),
    "a concept in two schemes": Fault(
        at("a"),
        "MaxCountConstraintComponent",
        SKOS + "inScheme",
        add=f"t:a skos:inScheme <{TAXONOMY}u> .",
    ),
    "a scheme that is no scheme": Fault(
        at("d"),
        "ClassConstraintComponent",
        SKOS + "inScheme",
        add=concept("d", scheme="w"),
    ),
    "two parents": Fault(
        at("c"), "MaxCountConstraintComponent", SKOS + "broader", add="t:c skos:broader t:a ."
    ),
    "a parent that is no concept": Fault(
        at("c"),
        "ClassConstraintComponent",
        SKOS + "broader",
        tax("c", "skos:broader t:b", "skos:broader t:x"),
    ),
    "a node typed as neither a concept nor a scheme": Fault(
        at("d"), "OrConstraintComponent", add='t:d skos:notation "t.d" .'
    ),
    "a scheme with no notation": Fault(
        f"{TAXONOMY}t",
        "MinCountConstraintComponent",
        T_NOTATION,
        tax("scheme t", ' skos:notation "t" ;', ""),
    ),
    "a scheme with a prefLabel in French": Fault(
        f"{TAXONOMY}t",
        "LanguageInConstraintComponent",
        T_LABEL,
        tax("scheme t", '"t"@es', '"t"@fr'),
    ),
}
ONTOLOGY_FAULTS = {
    "a class with no Spanish label": Fault(
        SL + "C", "MinCountConstraintComponent", O_LABEL, onto("C", ', "C"@es', "")
    ),
    "a class with no comment": Fault(
        SL + "C", "MinCountConstraintComponent", O_COMMENT, onto("C", 'rdfs:comment "C"@en', "")
    ),
    "a class with a label in French": Fault(
        SL + "C", "LanguageInConstraintComponent", O_LABEL, onto("C", '"C"@es', '"C"@fr')
    ),
    "a class with two English labels": Fault(
        SL + "C", "UniqueLangConstraintComponent", O_LABEL, onto("C", '"C"@es', '"CC"@en')
    ),
    "a class outside the namespace": Fault(
        "https://semantic-lab.example/other#C",
        "PatternConstraintComponent",
        add="<https://semantic-lab.example/other#C> a owl:Class ;"
        f' rdfs:label {LABELS.format("C")} ; rdfs:comment "C"@en .',
    ),
    "a class with two parents": Fault(
        SL + "C",
        "MaxCountConstraintComponent",
        RDFS + "subClassOf",
        add="sl:C rdfs:subClassOf sl:Other .",
    ),
    "a parent that is no class": Fault(
        SL + "C",
        "ClassConstraintComponent",
        RDFS + "subClassOf",
        onto("C", "sl:Owner", "sl:Nowhere"),
    ),
    "an object property with two domains": Fault(
        SL + "op", "MaxCountConstraintComponent", O_DOMAIN, add="sl:op rdfs:domain sl:Other ."
    ),
    "an object property with no domain": Fault(
        SL + "op", "MinCountConstraintComponent", O_DOMAIN, onto("op", "rdfs:domain sl:Owner ;", "")
    ),
    "an object property whose domain is no class": Fault(
        SL + "op",
        "ClassConstraintComponent",
        O_DOMAIN,
        onto("op", "domain sl:Owner", "domain sl:Nowhere"),
    ),
    "an object property whose range is xsd:string": Fault(
        SL + "op", "OrConstraintComponent", O_RANGE, onto("op", "range sl:C", "range xsd:string")
    ),
    "an object property with two ranges": Fault(
        SL + "op", "MaxCountConstraintComponent", O_RANGE, add="sl:op rdfs:range sl:Other ."
    ),
    "an object property with no comment": Fault(
        SL + "op", "MinCountConstraintComponent", O_COMMENT, onto("op", 'rdfs:comment "op"@en', "")
    ),
    "a datatype property whose range is xsd:float": Fault(
        SL + "dp", "InConstraintComponent", O_RANGE, onto("dp", "xsd:string", "xsd:float")
    ),
    "a datatype property with no range": Fault(
        SL + "dp",
        "MinCountConstraintComponent",
        O_RANGE,
        onto("dp", "rdfs:range xsd:string ;", ""),
    ),
    "a datatype property with two domains": Fault(
        SL + "dp", "MaxCountConstraintComponent", O_DOMAIN, add="sl:dp rdfs:domain sl:Other ."
    ),
    "a datatype property with a label in French": Fault(
        SL + "dq", "LanguageInConstraintComponent", O_LABEL, onto("dq", '"dq"@es', '"dq"@fr')
    ),
}


def test_the_repository_taxonomies_conform(shapes: Graph) -> None:
    assert validate(taxonomy_graph(TAXONOMY_DIRECTORY), shapes) == ()


def test_the_repository_ontology_conforms(shapes: Graph) -> None:
    assert validate(ontology_graph(ONTOLOGY_FILE), shapes) == ()


def test_the_graph_the_taxonomy_faults_start_from_conforms(shapes: Graph) -> None:
    assert validate(graph_of(TAXONOMY_LINES), shapes) == ()


def test_the_graph_the_ontology_faults_start_from_conforms(shapes: Graph) -> None:
    assert validate(graph_of(ONTOLOGY_LINES), shapes) == ()


def one_violation(lines: dict[str, str], fault: Fault, shapes: Graph) -> None:
    found = [(v.focus, v.constraint, v.path) for v in validate(graph_of(lines, fault), shapes)]
    assert found == [(fault.focus, fault.constraint, fault.path)]


@pytest.mark.parametrize("name", TAXONOMY_FAULTS)
def test_a_taxonomy_fault_is_caught_by_its_rule(name: str, shapes: Graph) -> None:
    one_violation(TAXONOMY_LINES, TAXONOMY_FAULTS[name], shapes)


@pytest.mark.parametrize("name", ONTOLOGY_FAULTS)
def test_an_ontology_fault_is_caught_by_its_rule(name: str, shapes: Graph) -> None:
    one_violation(ONTOLOGY_LINES, ONTOLOGY_FAULTS[name], shapes)


@pytest.fixture(scope="module")
def ontology_rdf() -> Graph:
    return ontology_graph(ONTOLOGY_FILE)


@pytest.fixture(scope="module")
def fault_graph(
    dataset: Dataset, taxonomy: Taxonomy, ontology: Ontology, mapping: Mapping
) -> Graph:
    return data_graph(data_faults.fault_sample(dataset), taxonomy, ontology, mapping)


@pytest.fixture(scope="module")
def data_shapes(shapes: Graph) -> Graph:
    return data_faults.data_group(shapes)


def test_the_first_200_orders_conform(
    dataset: Dataset,
    taxonomy: Taxonomy,
    ontology: Ontology,
    mapping: Mapping,
    shapes: Graph,
    ontology_rdf: Graph,
) -> None:
    sample = data_graph(first_orders(dataset, 200), taxonomy, ontology, mapping)
    assert validate(sample, shapes, ontology_rdf) == ()


def test_the_sample_the_data_faults_start_from_conforms(
    fault_graph: Graph, shapes: Graph, ontology_rdf: Graph
) -> None:
    assert validate(fault_graph, shapes, ontology_rdf) == ()


def test_the_data_group_holds_the_shape_of_each_class(data_shapes: Graph) -> None:
    targets = set(data_shapes.objects(None, SH.targetClass))
    assert len(targets) == 14


def test_every_class_with_a_table_has_a_closed_shape(shapes: Graph, mapping: Mapping) -> None:
    for entry in mapping.classes:
        owners = list(shapes.subjects(SH.targetClass, URIRef(entry.iri)))
        assert len(owners) == 1, entry.iri
        assert (owners[0], RDF.type, SH.NodeShape) in shapes
        # A conditional entry is a kind of product: it adds rules and leaves the closing to Product.
        closed = (owners[0], SH.closed, Literal(True)) in shapes
        assert closed == (entry.when is None), entry.iri


@pytest.mark.parametrize("name", CHANGES)
def test_a_data_fault_is_caught_by_its_rule(
    name: str, fault_graph: Graph, data_shapes: Graph, ontology_rdf: Graph
) -> None:
    data_faults.check_exact(CHANGES[name], fault_graph, data_shapes, ontology_rdf)


@pytest.mark.parametrize("name", KINDS)
def test_every_property_of_every_class_is_checked(
    name: str, fault_graph: Graph, data_shapes: Graph, ontology_rdf: Graph
) -> None:
    data_faults.check_contained(KINDS[name], fault_graph, data_shapes, ontology_rdf)
