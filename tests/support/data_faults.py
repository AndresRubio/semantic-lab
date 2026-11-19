"""Faulty examples for the data shapes.

A fault changes a copy of the sample's data graph and returns the violations it should cause.
The cases that carry the plan's table run on a small sample, because pyshacl parses every SPARQL
rule again for each batch: the sample is the first orders with only the lots a batch or an
incident names, and the data shapes run without the taxonomy shapes. The full shapes and larger
samples are checked in `tests/guards/test_shapes.py`.
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import SKOS, XSD

from semantic_lab.domain.mapping import Mapping
from semantic_lab.domain.ontology import NAMESPACE, Ontology
from semantic_lab.domain.records import Dataset
from semantic_lab.domain.sample import first_orders
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.rdf.export import DATA, export
from semantic_lab.rdf.shacl import validate
from semantic_lab.rdf.taxonomy import taxonomy_graph
from tests.support.paths import TAXONOMY_DIRECTORY

TAXONOMY = "https://semantic-lab.example/taxonomy/"
SLN = Namespace(NAMESPACE)
NODES = Namespace(DATA)
GEO = Namespace(TAXONOMY + "geo#")
PROCESS = Namespace(TAXONOMY + "process#")
CATEGORY = Namespace(TAXONOMY + "category#")
FLAVOUR = Namespace(TAXONOMY + "flavour#")
CLASSES = (
    "Cooperative",
    "Certification",
    "Farm",
    "Shipment",
    "Lot",
    "Product",
    "RoastBatch",
    "BatchComponent",
    "Customer",
    "Order",
    "OrderLine",
    "QualityIncident",
)
FAULT_ORDERS = 3

# A violation as `validate` reports it: focus, constraint component, path (None if not one IRI).
Hit = tuple[URIRef, str, str | None]
Change = Callable[[Graph], list[Hit]]


def hit(focus: Any, constraint: str, path: Any = None) -> Hit:
    """A violation. A path is a property of the ontology by its name, or any other IRI."""
    if isinstance(path, str) and not isinstance(path, URIRef):
        path = SLN[path]
    return (URIRef(focus), constraint + "ConstraintComponent", path)


def data_graph(sample: Dataset, taxonomy: Taxonomy, ontology: Ontology, mapping: Mapping) -> Graph:
    """The export of a sample and the taxonomy graph: what the shapes are checked against."""
    graph = Graph()
    graph += export(sample, taxonomy, ontology, mapping)
    graph += taxonomy_graph(TAXONOMY_DIRECTORY)
    return graph


def fault_sample(dataset: Dataset) -> Dataset:
    """The first orders, without the lots that no batch component or incident names."""
    sample = first_orders(dataset, FAULT_ORDERS)
    used = {c.lot_code for c in sample.roast_batch_lots}
    used |= {i.lot_code for i in sample.quality_incidents}
    return replace(
        sample,
        lots=tuple(lot for lot in sample.lots if lot.code in used),
        lot_farms=tuple(link for link in sample.lot_farms if link.lot_code in used),
    )


def copy(graph: Graph) -> Graph:
    duplicate = Graph()
    duplicate += graph
    return duplicate


def violations(graph: Graph, shapes: Graph, ontology: Graph) -> Counter[Hit]:
    return Counter(
        (URIRef(v.focus), v.constraint, None if v.path is None else URIRef(v.path))
        for v in validate(graph, shapes, ontology)
    )


def members(g: Graph, name: str) -> list[URIRef]:
    return sorted(s for s in g.subjects(RDF.type, SLN[name]) if isinstance(s, URIRef))


def first(g: Graph, name: str) -> URIRef:
    return members(g, name)[0]


def get(g: Graph, node: URIRef, name: str) -> URIRef:
    value = g.value(node, SLN[name])
    assert isinstance(value, URIRef), f"{node} has no {name} node"
    return value


def py(g: Graph, node: URIRef, name: str) -> Any:
    value = g.value(node, SLN[name])
    assert isinstance(value, Literal), f"{node} has no {name} value"
    return value.toPython()


def put(g: Graph, node: URIRef, name: str, value: Any) -> None:
    g.set((node, SLN[name], value))


def region_of(g: Graph, lot: URIRef) -> URIRef:
    return get(g, get(g, lot, "producedBy"), "inRegion")


def pointing_at(g: Graph, name: str, node: URIRef) -> list[URIRef]:
    return sorted(s for s in g.subjects(SLN[name], node) if isinstance(s, URIRef))


def batches_of(g: Graph, product: URIRef) -> list[URIRef]:
    return pointing_at(g, "batchOf", product)


def components_of(g: Graph, batch: URIRef) -> list[URIRef]:
    return pointing_at(g, "componentOf", batch)


def lines_of(g: Graph, batch: URIRef) -> list[URIRef]:
    return pointing_at(g, "fromBatch", batch)


def is_a(g: Graph, node: URIRef, name: str) -> bool:
    return (node, RDF.type, SLN[name]) in g


def batch_of(g: Graph, kind: str) -> URIRef:
    return next(b for b in members(g, "RoastBatch") if is_a(g, get(g, b, "batchOf"), kind))


def unused_cooperative(g: Graph) -> URIRef:
    """A cooperative whose region is no batch product's origin: moving it breaks no batch rule."""
    origins = {g.value(get(g, b, "batchOf"), SLN.originRegion) for b in members(g, "RoastBatch")}
    return next(c for c in members(g, "Cooperative") if get(g, c, "inRegion") not in origins)


def unbatched(g: Graph, name: str) -> URIRef:
    return next(p for p in members(g, name) if not batches_of(g, p))


def ghost(g: Graph, scheme: str, broader: URIRef | None = None) -> URIRef:
    """A concept of a scheme that no triple types as a skos:Concept."""
    node = URIRef(f"{TAXONOMY}{scheme}#ghost")
    g.add((node, SKOS.inScheme, URIRef(TAXONOMY + scheme)))
    if broader is not None:
        g.add((node, SKOS.broader, broader))
    return node


CHANGES: dict[str, Change] = {}


def fault(change: Change) -> Change:
    CHANGES[change.__name__.replace("_", " ")] = change
    return change


@fault
def a_lot_weighing_minus_one(g: Graph) -> list[Hit]:
    lot = first(g, "Lot")
    put(g, lot, "weightKg", Literal(Decimal(-1)))
    return [hit(lot, "MinExclusive", "weightKg")]


@fault
def a_shipment_arriving_before_it_departs(g: Graph) -> list[Hit]:
    shipment = first(g, "Shipment")
    put(g, shipment, "arrivedOn", Literal(py(g, shipment, "departedOn") - timedelta(days=1)))
    return [hit(shipment, "LessThan", "departedOn")]


@fault
def a_certification_ending_before_it_starts(g: Graph) -> list[Hit]:
    certification = next(c for c in members(g, "Certification") if (c, SLN.validUntil, None) in g)
    start = py(g, certification, "validFrom")
    put(g, certification, "validUntil", Literal(start - timedelta(days=1)))
    return [hit(certification, "LessThan", "validFrom")]


@fault
def a_certification_standard_that_is_not_listed(g: Graph) -> list[Hit]:
    certification = first(g, "Certification")
    put(g, certification, "standard", Literal("bio"))
    return [hit(certification, "In", "standard")]


@fault
def a_customer_segment_that_is_not_listed(g: Graph) -> list[Hit]:
    customer = first(g, "Customer")
    put(g, customer, "segment", Literal("bar"))
    return [hit(customer, "In", "segment")]


@fault
def an_incident_kind_that_is_not_recall(g: Graph) -> list[Hit]:
    incident = first(g, "QualityIncident")
    put(g, incident, "kind", Literal("complaint"))
    return [hit(incident, "In", "kind")]


@fault
def a_customer_code_in_the_wrong_format(g: Graph) -> list[Hit]:
    customer = first(g, "Customer")
    put(g, customer, "code", Literal("X1"))
    return [hit(customer, "Pattern", "code")]


@fault
def a_farm_altitude_written_as_a_string(g: Graph) -> list[Hit]:
    farm = first(g, "Farm")
    put(g, farm, "altitudeMetres", Literal("1500"))
    # A string is no number, so the comparison with 0 fails as well.
    return [hit(farm, "Datatype", "altitudeMetres"), hit(farm, "MinExclusive", "altitudeMetres")]


@fault
def a_farm_at_altitude_zero(g: Graph) -> list[Hit]:
    farm = first(g, "Farm")
    put(g, farm, "altitudeMetres", Literal(0))
    return [hit(farm, "MinExclusive", "altitudeMetres")]


@fault
def every_class_refuses_a_property_it_does_not_have(g: Graph) -> list[Hit]:
    nodes = [first(g, name) for name in CLASSES]
    for node in nodes:
        g.add((node, SLN.colour, Literal("brown")))
    return [hit(node, "Closed", "colour") for node in nodes]


@fault
def an_order_line_of_an_order_that_does_not_exist(g: Graph) -> list[Hit]:
    line = next(
        item
        for item in members(g, "OrderLine")
        if len(pointing_at(g, "lineOf", get(g, item, "lineOf"))) > 1
    )
    put(g, line, "lineOf", NODES["order/O-00000"])
    return [hit(line, "Class", "lineOf")]


@fault
def a_lot_with_a_second_cooperative(g: Graph) -> list[Hit]:
    lot = first(g, "Lot")
    other = next(c for c in members(g, "Cooperative") if c != get(g, lot, "producedBy"))
    g.add((lot, SLN.producedBy, other))
    return [hit(lot, "MaxCount", "producedBy"), hit(lot, "Equals")]


@fault
def a_blend_with_an_origin_region(g: Graph) -> list[Hit]:
    blend = unbatched(g, "Blend")
    g.add((blend, SLN.originRegion, region_of(g, first(g, "Lot"))))
    return [hit(blend, "MaxCount", "originRegion")]


@fault
def a_single_lot_product_without_an_origin_region(g: Graph) -> list[Hit]:
    product = first(g, "SingleLotProduct")
    g.remove((product, SLN.originRegion, None))
    return [hit(product, "MinCount", "originRegion")]


@fault
def a_single_lot_product_with_two_origin_regions(g: Graph) -> list[Hit]:
    product = unbatched(g, "SingleLotProduct")
    other = next(r for r in (GEO.guji, GEO.sidama) if (product, SLN.originRegion, r) not in g)
    g.add((product, SLN.originRegion, other))
    # The shape of the product and the shape of its kind each count the values.
    return [hit(product, "MaxCount", "originRegion")] * 2


@fault
def a_product_without_its_blend_type(g: Graph) -> list[Hit]:
    blend = first(g, "Blend")
    g.remove((blend, RDF.type, SLN.Blend))
    return [hit(blend, "Xone")]


@fault
def a_product_that_is_a_blend_and_a_single_lot_product(g: Graph) -> list[Hit]:
    blend = unbatched(g, "Blend")
    g.add((blend, RDF.type, SLN.SingleLotProduct))
    return [hit(blend, "Xone"), hit(blend, "MinCount", "originRegion")]


@fault
def a_blend_in_a_category_outside_the_blends(g: Graph) -> list[Hit]:
    blend = first(g, "Blend")
    put(g, blend, "category", CATEGORY.decaf)
    return [hit(blend, "HasValue")]


@fault
def a_product_in_the_root_category(g: Graph) -> list[Hit]:
    product = first(g, "SingleLotProduct")
    put(g, product, "category", CATEGORY.coffee)
    return [hit(product, "Node", "category"), hit(CATEGORY.coffee, "MinCount", SKOS.broader)]


@fault
def a_cooperative_in_a_country(g: Graph) -> list[Hit]:
    cooperative = unused_cooperative(g)
    country = g.value(get(g, cooperative, "inRegion"), SKOS.broader)
    put(g, cooperative, "inRegion", country)
    return [hit(cooperative, "Node", "inRegion"), hit(country, "MinCount")]


@fault
def a_cooperative_in_a_place_below_a_region(g: Graph) -> list[Hit]:
    cooperative = unused_cooperative(g)
    below = NODES["below"]
    g.add((below, RDF.type, SKOS.Concept))
    g.add((below, SKOS.inScheme, URIRef(TAXONOMY + "geo")))
    g.add((below, SKOS.broader, get(g, cooperative, "inRegion")))
    put(g, cooperative, "inRegion", below)
    return [hit(cooperative, "Node", "inRegion"), hit(below, "MaxCount")]


@fault
def a_cooperative_in_a_category_two_levels_down(g: Graph) -> list[Hit]:
    cooperative = unused_cooperative(g)
    put(g, cooperative, "inRegion", CATEGORY.microlot)
    return [hit(cooperative, "Node", "inRegion"), hit(CATEGORY.microlot, "HasValue", SKOS.inScheme)]


@fault
def a_cooperative_in_a_region_that_is_no_concept(g: Graph) -> list[Hit]:
    cooperative = unused_cooperative(g)
    node = ghost(g, "geo", GEO.ethiopia)
    put(g, cooperative, "inRegion", node)
    return [hit(cooperative, "Node", "inRegion"), hit(node, "Class")]


@fault
def a_lot_processed_by_a_flavour(g: Graph) -> list[Hit]:
    lot = first(g, "Lot")
    put(g, lot, "process", FLAVOUR.citrus)
    return [hit(lot, "Node", "process"), hit(FLAVOUR.citrus, "HasValue", SKOS.inScheme)]


@fault
def a_lot_processed_by_a_region(g: Graph) -> list[Hit]:
    lot = first(g, "Lot")
    put(g, lot, "process", GEO.yirgacheffe)
    return [hit(lot, "Node", "process"), hit(GEO.yirgacheffe, "HasValue", SKOS.inScheme)]


@fault
def a_lot_processed_by_something_that_is_no_concept(g: Graph) -> list[Hit]:
    lot = first(g, "Lot")
    node = ghost(g, "process")
    put(g, lot, "process", node)
    return [hit(lot, "Node", "process"), hit(node, "Class")]


@fault
def a_product_in_a_process_as_its_category(g: Graph) -> list[Hit]:
    product = first(g, "SingleLotProduct")
    put(g, product, "category", PROCESS["red-honey"])
    return [hit(product, "Node", "category"), hit(PROCESS["red-honey"], "HasValue", SKOS.inScheme)]


@fault
def a_product_in_a_category_that_is_no_concept(g: Graph) -> list[Hit]:
    product = first(g, "SingleLotProduct")
    node = ghost(g, "category", CATEGORY["single-origin"])
    put(g, product, "category", node)
    return [hit(product, "Node", "category"), hit(node, "Class")]


@fault
def a_product_with_a_flavour_that_has_narrower_flavours(g: Graph) -> list[Hit]:
    product = first(g, "Product")
    g.add((product, SLN.flavourNote, FLAVOUR.berry))
    return [hit(product, "Node", "flavourNote"), hit(FLAVOUR.berry, "MaxCount")]


@fault
def a_product_with_a_region_as_a_flavour(g: Graph) -> list[Hit]:
    product = first(g, "Product")
    g.add((product, SLN.flavourNote, GEO.yirgacheffe))
    return [hit(product, "Node", "flavourNote"), hit(GEO.yirgacheffe, "HasValue", SKOS.inScheme)]


@fault
def a_product_with_a_flavour_that_is_no_concept(g: Graph) -> list[Hit]:
    product = first(g, "Product")
    node = ghost(g, "flavour")
    g.add((product, SLN.flavourNote, node))
    return [hit(product, "Node", "flavourNote"), hit(node, "Class")]


@fault
def a_lot_harvested_on_a_farm_of_another_cooperative(g: Graph) -> list[Hit]:
    lot = first(g, "Lot")
    cooperative = get(g, lot, "producedBy")
    farm = next(f for f in members(g, "Farm") if get(g, f, "memberOf") != cooperative)
    g.remove((lot, SLN.harvestedFrom, None))
    g.add((lot, SLN.harvestedFrom, farm))
    # Equals reports a value of each side that the other lacks.
    return [hit(lot, "Equals")] * 2


@fault
def an_order_line_filled_from_a_batch_of_another_product(g: Graph) -> list[Hit]:
    line = first(g, "OrderLine")
    product = get(g, get(g, line, "fromBatch"), "batchOf")
    kg = py(g, line, "kg")

    def room(batch: URIRef) -> bool:
        return py(g, batch, "outputKg") - sum(py(g, x, "kg") for x in lines_of(g, batch)) >= kg

    batch = next(b for b in members(g, "RoastBatch") if get(g, b, "batchOf") != product and room(b))
    put(g, line, "fromBatch", batch)
    return [hit(line, "Equals")] * 2


@fault
def a_component_share_raised_by_a_hundredth(g: Graph) -> list[Hit]:
    batch = batch_of(g, "Blend")
    component = components_of(g, batch)[0]
    put(g, component, "share", Literal(py(g, component, "share") + Decimal("0.01")))
    return [hit(batch, "SPARQL")]


@fault
def a_component_share_of_zero(g: Graph) -> list[Hit]:
    batch = batch_of(g, "Blend")
    component = components_of(g, batch)[0]
    put(g, component, "share", Literal(Decimal(0)))
    return [hit(component, "MinExclusive", "share"), hit(batch, "SPARQL")]


@fault
def a_component_share_above_one(g: Graph) -> list[Hit]:
    batch = batch_of(g, "SingleLotProduct")
    component = components_of(g, batch)[0]
    put(g, component, "share", Literal(Decimal("1.5")))
    return [hit(component, "MaxInclusive", "share"), hit(batch, "SPARQL")]


@fault
def a_batch_that_produced_less_than_its_lines_took(g: Graph) -> list[Hit]:
    batch = first(g, "RoastBatch")
    assert lines_of(g, batch)
    put(g, batch, "outputKg", Literal(Decimal("0.01")))
    return [hit(batch, "SPARQL")]


@fault
def a_single_lot_batch_with_a_second_component(g: Graph) -> list[Hit]:
    batch = batch_of(g, "SingleLotProduct")
    component = components_of(g, batch)[0]
    second = NODES["batch-component/second"]
    g.add((second, RDF.type, SLN.BatchComponent))
    g.add((second, SLN.componentOf, batch))
    g.add((second, SLN.fromLot, get(g, component, "fromLot")))
    put(g, second, "share", Literal(Decimal("0.5")))
    put(g, component, "share", Literal(Decimal("0.5")))
    return [hit(batch, "SPARQL")]


@fault
def a_blend_batch_with_one_component(g: Graph) -> list[Hit]:
    batch = batch_of(g, "Blend")
    kept, *dropped = components_of(g, batch)
    for component in dropped:
        g.remove((component, None, None))
    put(g, kept, "share", Literal(Decimal(1)))
    return [hit(batch, "SPARQL")]


@fault
def a_single_lot_batch_from_a_lot_of_another_region(g: Graph) -> list[Hit]:
    batch = batch_of(g, "SingleLotProduct")
    component = components_of(g, batch)[0]
    region = g.value(get(g, batch, "batchOf"), SLN.originRegion)
    lot = next(item for item in members(g, "Lot") if region_of(g, item) != region)
    put(g, component, "fromLot", lot)
    return [hit(batch, "SPARQL")]


@fault
def a_batch_with_no_component(g: Graph) -> list[Hit]:
    batch = batch_of(g, "SingleLotProduct")
    for component in components_of(g, batch):
        g.remove((component, None, None))
    return [hit(batch, "MinCount")]


@fault
def an_order_with_no_line(g: Graph) -> list[Hit]:
    order = first(g, "Order")
    for line in pointing_at(g, "lineOf", order):
        g.remove((line, None, None))
    return [hit(order, "MinCount")]


# The generic cases below take every property of every class, each on a node of its own where
# the class has enough of them, and damage it in one way, all in one graph. They expect what the
# plan's table says of that damage, and more violations may follow.


@dataclass(frozen=True)
class Slot:
    name: str
    predicate: URIRef
    node: URIRef
    required: bool
    several: bool


def slots(g: Graph) -> list[Slot]:
    found = []
    for name in CLASSES:
        nodes = members(g, name)
        predicates = sorted(
            {p for n in nodes for p in g.predicates(n) if isinstance(p, URIRef) and p != RDF.type}
        )
        for index, predicate in enumerate(predicates):
            holders = [n for n in nodes if (n, predicate, None) in g]
            found.append(
                Slot(
                    name,
                    predicate,
                    holders[index % len(holders)],
                    required=len(holders) == len(nodes),
                    several=any(len(list(g.objects(n, predicate))) > 1 for n in nodes),
                )
            )
    return found


def local(predicate: URIRef) -> str:
    return str(predicate).removeprefix(NAMESPACE)


def another(g: Graph, slot: Slot) -> Any:
    """A value for the property other than the one the node has."""
    current = g.value(slot.node, slot.predicate)
    seen = {o for n in members(g, slot.name) for o in g.objects(n, slot.predicate)}
    others = sorted(seen - {current}, key=str)
    if others:
        return others[0]
    if not isinstance(current, Literal):
        return NODES["nowhere"]
    value = current.toPython()
    if isinstance(value, str):
        return Literal(value + "x")
    if isinstance(value, date):
        return Literal(value + timedelta(days=1))
    return Literal(value + 1)


def a_value_missing(g: Graph) -> list[Hit]:
    found = []
    for slot in slots(g):
        if slot.required:
            g.remove((slot.node, slot.predicate, None))
            found.append(hit(slot.node, "MinCount", local(slot.predicate)))
    return found


def a_second_value(g: Graph) -> list[Hit]:
    found = []
    for slot in slots(g):
        if not slot.several:
            g.add((slot.node, slot.predicate, another(g, slot)))
            found.append(hit(slot.node, "MaxCount", local(slot.predicate)))
    return found


def a_value_of_the_wrong_kind(g: Graph) -> list[Hit]:
    found = []
    for slot in slots(g):
        current = g.value(slot.node, slot.predicate)
        if isinstance(current, Literal):
            text = current.datatype in (None, XSD.string)
            wrong: Any = Literal(7) if text else Literal("x")
            constraint = "Datatype"
        else:
            wrong = NODES["nowhere"]
            constraint = "Node" if (current, RDF.type, SKOS.Concept) in g else "Class"
        g.remove((slot.node, slot.predicate, None))
        g.add((slot.node, slot.predicate, wrong))
        found.append(hit(slot.node, constraint, local(slot.predicate)))
    return found


def a_code_in_the_wrong_format(g: Graph) -> list[Hit]:
    found = []
    for slot in slots(g):
        if slot.predicate == SLN.code:
            put(g, slot.node, "code", Literal("X1"))
            found.append(hit(slot.node, "Pattern", "code"))
    return found


# The properties that must be above 0, and the two that must be at least 1.
MINIMUM = {
    **dict.fromkeys(
        (
            "altitudeMetres",
            "weightKg",
            "pricePerKg",
            "bagWeightGrams",
            "listPrice",
            "outputKg",
            "costPerKg",
            "share",
            "unitPrice",
            "amount",
            "kg",
        ),
        "MinExclusive",
    ),
    "lineNo": "MinInclusive",
    "bags": "MinInclusive",
}


def a_number_that_is_not_positive(g: Graph) -> list[Hit]:
    found = []
    for slot in slots(g):
        constraint = MINIMUM.get(local(slot.predicate))
        if constraint is not None:
            current = g.value(slot.node, slot.predicate)
            assert isinstance(current, Literal)
            zero = Literal(0) if current.datatype == XSD.integer else Literal(Decimal(0))
            g.set((slot.node, slot.predicate, zero))
            found.append(hit(slot.node, constraint, local(slot.predicate)))
    return found


KINDS: dict[str, Change] = {
    f.__name__.replace("_", " "): f
    for f in (
        a_value_missing,
        a_second_value,
        a_value_of_the_wrong_kind,
        a_code_in_the_wrong_format,
        a_number_that_is_not_positive,
    )
}


def check_exact(change: Change, sample: Graph, shapes: Graph, ontology: Graph) -> None:
    """The change causes the violations it names and no others."""
    graph = copy(sample)
    expected = Counter(change(graph))
    found = violations(graph, shapes, ontology)
    assert found == expected, f"found {sorted(map(str, found.elements()))}"


def check_contained(change: Change, sample: Graph, shapes: Graph, ontology: Graph) -> None:
    """The change causes at least the violations it names."""
    graph = copy(sample)
    expected = change(graph)
    found = violations(graph, shapes, ontology)
    missing = [h for h in expected if h not in found]
    assert not missing, f"not reported: {[(str(f), c, str(p)) for f, c, p in missing]}"
