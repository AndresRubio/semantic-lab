import pytest
from rdflib import Graph
from rdflib.namespace import SH

from semantic_lab.domain.errors import OntologyError
from semantic_lab.domain.ontology import NAMESPACE
from semantic_lab.rdf.shacl import Violation, data_shapes, validate

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


def test_the_line_ends_with_a_value_the_message_does_not_hold() -> None:
    violation = Violation("f", "SPARQLConstraintComponent", None, "0.95", "The shares sum to 1.")
    assert violation.line() == "f SPARQLConstraintComponent: The shares sum to 1. (value 0.95)"


def test_the_line_does_not_repeat_the_focus_as_its_value() -> None:
    violation = Violation("f", "OrConstraintComponent", None, "f", "A node must be typed.")
    assert violation.line() == "f OrConstraintComponent: A node must be typed."


def test_a_blank_node_is_no_value() -> None:
    shapes = graph(
        """
ex:ThingShape a sh:NodeShape ; sh:targetClass ex:Thing ;
    sh:property [ sh:path ex:part ; sh:class ex:Part ; sh:message "A part is a Part." ] .
"""
    )
    found = validate(graph("ex:a a ex:Thing ; ex:part [ rdfs:label 1 ] ."), shapes)
    assert [violation.value for violation in found] == [None]
    assert found[0].line() == f"{EX}a ClassConstraintComponent {EX}part: A part is a Part."


@pytest.mark.parametrize(
    "message", ['It cannot have value: Literal("0.95", datatype=xsd:decimal)', "Value <0.95> is odd"]
)
def test_the_line_does_not_repeat_a_value_the_message_holds(message: str) -> None:
    violation = Violation("f", "ClosedConstraintComponent", "p", "0.95", message)
    assert violation.line() == f"f ClosedConstraintComponent p: {message}"


def test_a_rule_with_its_own_message_reports_the_value_it_selected() -> None:
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
    data = graph('ex:a a ex:Thing ; ex:name "a" ; ex:part 0.5, 0.25 .')
    lines = [violation.line() for violation in validate(data, shapes)]
    assert lines == [f"{EX}a SPARQLConstraintComponent: The parts sum to 1. (value 0.75)"]


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


def sparql_rule(where: str) -> Graph:
    return graph(
        SHAPES
        + f"""
ex:ThingShape sh:sparql [
    sh:message "A rule." ;
    sh:select \"\"\" SELECT $this WHERE {{ {where} }} \"\"\" ] .
"""
    )


def test_a_sparql_rule_with_a_syntax_error_raises_an_error_that_starts_with_validation() -> None:
    shapes = sparql_rule("$this ex:name ?name . FILTER (")
    with pytest.raises(OntologyError, match=r"^validation: ParseException: [^\n]+$"):
        validate(graph('ex:a a ex:Thing ; ex:name "a" .'), shapes)


def test_a_sparql_rule_with_an_undeclared_prefix_raises_an_error_that_starts_with_validation() -> (
    None
):
    shapes = sparql_rule("$this nope:name ?name .")
    with pytest.raises(OntologyError, match=r"^validation: Exception: [^\n]*nope[^\n]*$"):
        validate(graph('ex:a a ex:Thing ; ex:name "a" .'), shapes)


def test_the_data_shapes_target_the_fourteen_classes_and_nothing_else(shapes: Graph) -> None:
    group = data_shapes(shapes, NAMESPACE)
    targets = set(group.objects(None, SH.targetClass))
    assert len(targets) == 14
    assert all(str(target).startswith(NAMESPACE) for target in targets)
    for kind in (SH.targetSubjectsOf, SH.targetObjectsOf, SH.targetNode):
        assert not set(group.objects(None, kind)), kind


def test_the_data_shapes_keep_what_their_sparql_rules_name(shapes: Graph) -> None:
    group = data_shapes(shapes, NAMESPACE)
    for header in group.objects(None, SH.prefixes):
        assert set(group.objects(header, SH.declare)) == set(shapes.objects(header, SH.declare))
        for declaration in shapes.objects(header, SH.declare):
            assert set(group.predicate_objects(declaration)) == set(
                shapes.predicate_objects(declaration)
            )
    assert set(group.objects(None, SH.prefixes))


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
