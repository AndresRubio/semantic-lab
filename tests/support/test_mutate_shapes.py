import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import SH

from semantic_lab.domain.ontology import NAMESPACE
from tests.support import mutate_shapes
from tests.support.mutate_shapes import World

SHAPE = "https://semantic-lab.example/shapes#"


@pytest.fixture(scope="module")
def world() -> World:
    return mutate_shapes.load()


def test_the_constraints_are_the_rule_triples_once_each_in_a_stable_order(world: World) -> None:
    found = mutate_shapes.constraints(world.shapes)
    assert found == sorted(set(found), key=lambda t: tuple(map(str, t)))
    assert {predicate for _, predicate, _ in found} <= mutate_shapes.CONSTRAINTS
    assert (URIRef(SHAPE + "Lot"), SH.closed, Literal(True)) in found
    assert not [t for t in found if t[1] in (SH.path, SH.message, SH.targetClass)]


def test_a_removed_rule_is_caught_by_the_fault_that_proves_it(world: World) -> None:
    weight = next(
        shape
        for shape in world.shapes.subjects(SH.path, URIRef(NAMESPACE + "weightKg"))
        if (shape, SH.minExclusive, None) in world.shapes
    )
    rule = next(iter(world.shapes.triples((weight, SH.minExclusive, None))))
    assert rule in mutate_shapes.constraints(world.shapes)
    mutant = mutate_shapes.without(world.shapes, rule)
    assert rule not in mutant
    assert len(mutant) == len(world.shapes) - 1
    assert mutate_shapes.caught_by(mutant, world) == "a lot weighing minus one"


def test_a_mutant_the_given_checks_all_pass_is_caught_by_nothing(world: World) -> None:
    # sh:message is no constraint: without it every check still passes, so nothing catches it.
    message = next(iter(world.shapes.triples((None, SH.message, None))))
    mutant = mutate_shapes.without(world.shapes, message)
    first_three = dict(list(mutate_shapes.CHECKS.items())[:3])
    assert mutate_shapes.caught_by(mutant, world, first_three) is None


def test_opening_a_closed_shape_is_caught_by_the_fault_about_foreign_properties(
    world: World,
) -> None:
    lot = URIRef(SHAPE + "Lot")
    mutant = mutate_shapes.without(world.shapes, (lot, SH.closed, Literal(True)))
    # pyshacl refuses sh:ignoredProperties on an open shape, so the two leave together.
    assert (lot, SH.ignoredProperties, None) in world.shapes
    assert (lot, SH.ignoredProperties, None) not in mutant
    caught = mutate_shapes.caught_by(mutant, world)
    assert caught == "every class refuses a property it does not have"
