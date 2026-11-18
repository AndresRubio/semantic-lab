import dataclasses
from collections.abc import Callable
from typing import Any, NamedTuple

import pytest

from semantic_lab.domain.errors import MappingError
from semantic_lab.domain.mapping import (
    ClassEntry,
    Condition,
    Link,
    Mapping,
    PropertyEntry,
    build_mapping,
    problems,
)
from semantic_lab.domain.ontology import (
    CONCEPT,
    NAMESPACE,
    XSD_TYPES,
    Ontology,
    OntologyClass,
    Property,
    build_ontology,
)
from semantic_lab.domain.taxonomy import Concept, Taxonomy, build_taxonomy

STRING, INTEGER = XSD_TYPES[0], XSD_TYPES[1]
UNDER = ("category.blend",)
TABLES = ("cooperative", "farm", "lot_farm")


def iri(name: str) -> str:
    return NAMESPACE + name


def concept(key: str) -> Concept:
    return Concept(key, "category", f"https://example.test/{key}", "en", "es", (), None)


TAXONOMY: Taxonomy = build_taxonomy([concept("category.blend"), concept("category.decaf")])


def cls(name: str, parent: str | None = None) -> OntologyClass:
    return OntologyClass(iri(name), iri(parent) if parent else None)


def obj(name: str, domain: str, range: str) -> Property:
    return Property(iri(name), "object", iri(domain), range if range == CONCEPT else iri(range))


def data(name: str, domain: str | None, range: str = STRING) -> Property:
    return Property(iri(name), "datatype", iri(domain) if domain else None, range)


def entry(
    name: str, table: str, key: tuple[str, ...] = ("code",), when: Condition | None = None
) -> ClassEntry:
    return ClassEntry(iri(name), table, key, when)


def column(name: str, *columns: tuple[str, str]) -> PropertyEntry:
    return PropertyEntry(iri(name), columns, None)


def link(name: str, table: str, source: str, target: str) -> PropertyEntry:
    return PropertyEntry(iri(name), (), Link(table, source, target))


class World(NamedTuple):
    mapping: Mapping
    ontology: Ontology
    tables: tuple[str, ...] = TABLES

    def problems(self) -> tuple[str, ...]:
        return problems(self.mapping, self.ontology, TAXONOMY, self.tables)

    def with_terms(
        self,
        *,
        classes: tuple[OntologyClass, ...] = (),
        properties: tuple[Property, ...] = (),
        class_entries: tuple[ClassEntry, ...] = (),
        property_entries: tuple[PropertyEntry, ...] = (),
    ) -> "World":
        return World(
            build_mapping(
                (*self.mapping.classes, *class_entries),
                (*self.mapping.properties, *property_entries),
            ),
            build_ontology(
                (*self.ontology.classes, *classes), (*self.ontology.properties, *properties)
            ),
            self.tables,
        )

    def without_property(self, name: str) -> "World":
        return World(
            build_mapping(
                self.mapping.classes, (p for p in self.mapping.properties if p.iri != iri(name))
            ),
            build_ontology(
                self.ontology.classes, (p for p in self.ontology.properties if p.iri != iri(name))
            ),
            self.tables,
        )

    def with_class_entry(self, name: str, **changes: Any) -> "World":
        entries = [
            dataclasses.replace(e, **changes) if e.iri == iri(name) else e
            for e in self.mapping.classes
        ]
        return World(build_mapping(entries, self.mapping.properties), self.ontology, self.tables)


def base() -> World:
    ontology = build_ontology(
        [cls("Cooperative"), cls("Farm"), cls("SmallFarm", "Farm")],
        [
            obj("inRegion", "Cooperative", CONCEPT),
            obj("memberOf", "Farm", "Cooperative"),
            obj("neighbour", "Farm", "Farm"),
            data("code", None),
            data("name", None),
            data("altitudeMetres", "Farm", INTEGER),
        ],
    )
    mapping = build_mapping(
        [
            entry("Cooperative", "cooperative"),
            entry("Farm", "farm"),
            entry("SmallFarm", "farm", when=Condition("cooperative_code", UNDER)),
        ],
        [
            column("code", ("cooperative", "code"), ("farm", "code")),
            column("name", ("cooperative", "name"), ("farm", "name")),
            column("inRegion", ("cooperative", "region_key")),
            column("memberOf", ("farm", "cooperative_code")),
            column("altitudeMetres", ("farm", "altitude_m")),
            link("neighbour", "lot_farm", "lot_code", "farm_code"),
        ],
    )
    return World(mapping, ontology)


def lone(name: str = "Lone") -> tuple[OntologyClass, ...]:
    return (cls(name),)


def names(*short: str) -> str:
    return ", ".join(iri(n) for n in short)


# Each case starts from a world with no problem and adds the one fault it names. The two cases
# with two lines are faults that cannot stand alone: a table whose only class entry is
# conditional always has a conditional entry without its parent's.
CASES: dict[str, tuple[Callable[[World], World], tuple[str, ...]]] = {
    # 1: terms
    "class without an entry": (
        lambda w: w.with_terms(classes=lone()),
        (f"class {iri('Lone')} has no entry",),
    ),
    "property without an entry": (
        lambda w: w.with_terms(properties=(data("extra", "Farm"),)),
        (f"property {iri('extra')} has no entry",),
    ),
    "class entry for no term": (
        lambda w: w.with_terms(
            class_entries=(entry("Ghost", "farm", when=Condition("name", UNDER)),)
        ),
        (f"class entry {iri('Ghost')}: the ontology holds it as no term",),
    ),
    "class entry for a property": (
        lambda w: w.with_terms(
            class_entries=(entry("name", "farm", when=Condition("name", UNDER)),)
        ),
        (f"class entry {iri('name')}: the ontology holds it as a property",),
    ),
    "property entry for no term": (
        lambda w: w.with_terms(property_entries=(column("ghost"),)),
        (f"property entry {iri('ghost')}: the ontology holds it as no term",),
    ),
    "property entry for a class": (
        lambda w: w.with_terms(property_entries=(column("Farm"),)),
        (f"property entry {iri('Farm')}: the ontology holds it as a class",),
    ),
    # 2: class entries
    "class table is no data table": (
        lambda w: w.with_terms(classes=lone(), class_entries=(entry("Lone", "nope"),)),
        (f"class {iri('Lone')}: table nope is no data table",),
    ),
    "class key is not a column": (
        lambda w: w.with_terms(
            classes=lone(), class_entries=(entry("Lone", "shipment", ("nope",)),)
        ),
        (f"class {iri('Lone')}: nope is not a column of shipment",),
    ),
    "class condition column is not a column": (
        lambda w: w.with_class_entry("SmallFarm", when=Condition("nope", UNDER)),
        (f"class {iri('SmallFarm')}: nope is not a column of farm",),
    ),
    "class condition concept is unknown": (
        lambda w: w.with_class_entry(
            "SmallFarm", when=Condition("cooperative_code", ("category.nope",))
        ),
        (f"class {iri('SmallFarm')}: concept key category.nope is not in the taxonomy",),
    ),
    # 3: class entries against each other
    "two unconditional entries on a table": (
        lambda w: w.with_terms(classes=lone(), class_entries=(entry("Lone", "farm"),)),
        (f"table farm has 2 unconditional class entries: {names('Farm', 'Lone')}",),
    ),
    "conditional class without a parent": (
        lambda w: w.with_terms(
            classes=lone(), class_entries=(entry("Lone", "farm", when=Condition("name", UNDER)),)
        ),
        (f"class {iri('Lone')} is conditional but has no parent in the ontology",),
    ),
    "conditional class with another key than its parent": (
        lambda w: w.with_class_entry("SmallFarm", key=("name",)),
        (
            f"class {iri('SmallFarm')} is conditional, and its parent {iri('Farm')} has no "
            "unconditional entry on table farm with key ['name']",
        ),
    ),
    "conditional class on another table than its parent": (
        lambda w: w.with_class_entry(
            "SmallFarm", table="shipment", when=Condition("origin_port", UNDER)
        ),
        (
            f"class {iri('SmallFarm')} is conditional, and its parent {iri('Farm')} has no "
            "unconditional entry on table shipment with key ['code']",
        ),
    ),
    # 4: properties
    "property column on a table with no class": (
        lambda w: w.with_terms(
            properties=(data("port", "Farm"),),
            property_entries=(column("port", ("shipment", "origin_port")),),
        ),
        (
            f"property {iri('port')}: column shipment.origin_port is on a table with no "
            "unconditional class entry",
        ),
    ),
    "property column on a table with only a conditional class": (
        lambda w: w.with_terms(
            classes=(cls("Odd", "Farm"),),
            properties=(data("port", "Odd"),),
            class_entries=(entry("Odd", "shipment", when=Condition("origin_port", UNDER)),),
            property_entries=(column("port", ("shipment", "origin_port")),),
        ),
        (
            f"class {iri('Odd')} is conditional, and its parent {iri('Farm')} has no "
            "unconditional entry on table shipment with key ['code']",
            f"property {iri('port')}: column shipment.origin_port is on a table with no "
            "unconditional class entry",
        ),
    ),
    "property column is not a column": (
        lambda w: w.with_terms(
            properties=(data("oops", "Farm"),), property_entries=(column("oops", ("farm", "nope")),)
        ),
        (f"property {iri('oops')}: nope is not a column of farm",),
    ),
    "link table has a class entry": (
        lambda w: w.with_terms(
            classes=lone(),
            properties=(obj("tie", "Lone", "Lone"),),
            class_entries=(entry("Lone", "shipment"),),
            property_entries=(link("tie", "shipment", "origin_port", "destination_port"),),
        ),
        (f"property {iri('tie')}: link table shipment has a class entry",),
    ),
    "link table is no data table": (
        lambda w: w.with_terms(
            properties=(obj("tie", "Farm", "Farm"),),
            property_entries=(link("tie", "nope", "a", "b"),),
        ),
        (f"property {iri('tie')}: link table nope is no data table",),
    ),
    "link source is not a column": (
        lambda w: w.with_terms(
            properties=(obj("tie", "Farm", "Farm"),),
            property_entries=(link("tie", "shipment", "nope", "origin_port"),),
        ),
        (f"property {iri('tie')}: nope is not a column of shipment",),
    ),
    "link target is not a column": (
        lambda w: w.with_terms(
            properties=(obj("tie", "Farm", "Farm"),),
            property_entries=(link("tie", "shipment", "origin_port", "nope"),),
        ),
        (f"property {iri('tie')}: nope is not a column of shipment",),
    ),
    "link on a datatype property": (
        lambda w: w.with_terms(
            properties=(data("tie", "Farm"),),
            property_entries=(link("tie", "shipment", "origin_port", "destination_port"),),
        ),
        (f"property {iri('tie')} is a datatype property and cannot be a link",),
    ),
    # 5: coverage
    "column mapped by no property": (
        lambda w: w.without_property("altitudeMetres"),
        ("column farm.altitude_m is mapped by no property",),
    ),
    "column mapped by two properties": (
        lambda w: w.with_terms(
            properties=(data("again", "Farm"),),
            property_entries=(column("again", ("farm", "name")),),
        ),
        (f"column farm.name is mapped by 2 properties: {names('again', 'name')}",),
    ),
    "link column also mapped by a property": (
        lambda w: w.with_terms(
            properties=(data("again", "Farm"),),
            property_entries=(column("again", ("lot_farm", "farm_code")),),
        ),
        (
            f"column lot_farm.farm_code is mapped by 2 properties: {names('again', 'neighbour')}",
            f"property {iri('again')}: column lot_farm.farm_code is on a table with no "
            "unconditional class entry",
        ),
    ),
    "data table that is neither a class's nor a link's": (
        lambda w: w._replace(tables=(*w.tables, "shipment")),
        ("table shipment is neither a class's table nor a link's",),
    ),
}


def test_the_base_world_has_no_problem() -> None:
    assert base().problems() == ()


@pytest.mark.parametrize("case", CASES)
def test_each_fault_is_named_on_its_own_line(case: str) -> None:
    build, expected = CASES[case]
    assert build(base()).problems() == tuple(sorted(expected))


def test_the_lines_come_back_sorted() -> None:
    world = base().with_terms(classes=lone("Z"), properties=(data("a", "Farm"), data("b", "Farm")))
    found = world.problems()
    assert len(found) == 3
    assert found == tuple(sorted(found))


def test_by_default_every_data_table_must_be_mapped() -> None:
    found = problems(base().mapping, base().ontology, TAXONOMY)
    assert len(found) == 11
    assert all("is neither a class's table nor a link's" in line for line in found)


def test_postgres_columns_gathers_keys_conditions_properties_and_links() -> None:
    mapping = build_mapping(
        [entry("A", "farm", ("code", "name"), Condition("cooperative_code", UNDER))],
        [
            column("p", ("cooperative", "region_key")),
            link("q", "lot_farm", "lot_code", "farm_code"),
        ],
    )
    assert mapping.postgres_columns() == {
        ("farm", "code"),
        ("farm", "name"),
        ("farm", "cooperative_code"),
        ("cooperative", "region_key"),
        ("lot_farm", "lot_code"),
        ("lot_farm", "farm_code"),
    }


def test_build_mapping_sorts_by_iri_and_refuses_a_term_twice() -> None:
    mapping = build_mapping(
        [entry("B", "farm"), entry("A", "cooperative")], [column("z"), column("y")]
    )
    assert [c.iri for c in mapping.classes] == [iri("A"), iri("B")]
    assert [p.iri for p in mapping.properties] == [iri("y"), iri("z")]
    with pytest.raises(MappingError, match=iri("A")):
        build_mapping([entry("A", "farm"), entry("A", "cooperative")], [])
    with pytest.raises(MappingError, match=iri("z")):
        build_mapping([], [column("z"), column("z", ("farm", "name"))])
