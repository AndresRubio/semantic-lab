import pytest
from rdflib import Graph

from semantic_lab.domain.errors import OntologyError
from semantic_lab.rdf.shacl import Violation, validate

PREFIXES = """@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix ex: <https://semantic-lab.example/ex#> .
"""
SHAPES = PREFIXES + """
ex:ThingShape a sh:NodeShape ; sh:targetClass ex:Thing ;
    sh:property [ sh:path ex:name ; sh:minCount 1 ; sh:message "A thing needs a name." ] .
"""
EX = "https://semantic-lab.example/ex#"


def graph(text: str) -> Graph:
    return Graph().parse(data=PREFIXES + text, format="turtle")


def test_a_conforming_graph_has_no_violations() -> None:
    assert validate(graph('ex:a a ex:Thing ; ex:name "a" .'), graph(SHAPES)) == ()


def test_a_missing_value_is_one_violation_with_its_focus_constraint_and_path() -> None:
    result = validate(graph("ex:a a ex:Thing ."), graph(SHAPES))
    assert result == (
        Violation(
            focus=EX + "a",
            constraint="MinCountConstraintComponent",
            path=EX + "name",
            value=None,
            message="A thing needs a name.",
        ),
    )
    assert result[0].line() == f"{EX}a MinCountConstraintComponent {EX}name: A thing needs a name."


def test_a_violation_without_a_path_has_a_shorter_line() -> None:
    violation = Violation("f", "ClassConstraintComponent", None, None, "m")
    assert violation.line() == "f ClassConstraintComponent: m"


def test_an_ill_typed_number_in_a_sum_rule_raises_an_error_that_starts_with_validation() -> None:
    shapes = graph(
        SHAPES
        + """
ex:ThingShape sh:sparql [
    sh:message "The parts sum to 1." ;
    sh:select \"\"\"
        SELECT $this (SUM(?part) AS ?value)
        WHERE { $this <https://semantic-lab.example/ex#part> ?part . }
        GROUP BY $this
        HAVING (SUM(?part) != 1)
    \"\"\" ] .
"""
    )
    data = graph(
        'ex:a a ex:Thing ; ex:name "a" ; ex:part "abc"^^<http://www.w3.org/2001/XMLSchema#decimal> .'
    )
    with pytest.raises(OntologyError, match=r"^validation: (TypeError|SPARQLTypeError)[^\n]+$"):
        validate(data, shapes)


@pytest.mark.parametrize("order", [("a", "b"), ("b", "a")])
def test_violations_come_back_sorted_whatever_order_the_triples_were_added_in(
    order: tuple[str, str],
) -> None:
    data = Graph()
    for name in order:
        data += graph(f"ex:{name} a ex:Thing .")
    assert [v.focus for v in validate(data, graph(SHAPES))] == [EX + "a", EX + "b"]


def test_a_path_that_is_not_an_iri_is_reported_as_none() -> None:
    shapes = graph(
        SHAPES.replace("sh:path ex:name", "sh:path [ sh:inversePath ex:name ]")
    )
    (violation,) = validate(graph("ex:a a ex:Thing ."), shapes)
    assert violation.path is None


def test_a_malformed_shape_raises_an_error_that_starts_with_shapes() -> None:
    shapes = graph(SHAPES.replace("sh:minCount 1", 'sh:minCount "many"'))
    with pytest.raises(OntologyError, match=r"^shapes: [^\n]+$"):
        validate(graph("ex:a a ex:Thing ."), shapes)


def test_a_subclass_is_reported_by_its_parents_shape_only_with_the_ontology_graph() -> None:
    data = graph("ex:a a ex:SubThing .")
    ontology = graph("ex:SubThing rdfs:subClassOf ex:Thing .")
    assert validate(data, graph(SHAPES)) == ()
    assert [v.focus for v in validate(data, graph(SHAPES), ontology)] == [EX + "a"]


def test_the_data_graph_is_the_same_after_the_call() -> None:
    data = graph("ex:a a ex:SubThing .")
    before = set(data)
    validate(data, graph(SHAPES), graph("ex:SubThing rdfs:subClassOf ex:Thing ."))
    assert set(data) == before
