import dataclasses

import pytest
from rdflib import RDF, Graph, Literal, Namespace, URIRef

from semantic_lab.domain.errors import MappingError
from semantic_lab.domain.mapping import Mapping
from semantic_lab.domain.ontology import NAMESPACE, Ontology
from semantic_lab.domain.records import Dataset
from semantic_lab.domain.sample import first_orders
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.rdf.export import DATA, export

SL = Namespace(NAMESPACE)
DECIMAL = URIRef("http://www.w3.org/2001/XMLSchema#decimal")
DATE = URIRef("http://www.w3.org/2001/XMLSchema#date")
INTEGER = URIRef("http://www.w3.org/2001/XMLSchema#integer")


@pytest.fixture(scope="module")
def sample(dataset: Dataset) -> Dataset:
    return first_orders(dataset, 20)


@pytest.fixture(scope="module")
def graph(
    sample: Dataset, taxonomy: Taxonomy, ontology: Ontology, mapping: Mapping
) -> Graph:
    return export(sample, taxonomy, ontology, mapping)


def test_a_lot_becomes_a_typed_node_with_typed_values(graph: Graph, sample: Dataset, taxonomy: Taxonomy) -> None:
    lot = sample.lots[0]
    node = URIRef(f"{DATA}lot/{lot.code}")
    assert (node, RDF.type, SL.Lot) in graph
    assert graph.value(node, SL.producedBy) == URIRef(f"{DATA}cooperative/{lot.cooperative_code}")
    assert graph.value(node, SL.weightKg) == Literal(lot.weight_kg, datatype=DECIMAL)
    assert graph.value(node, SL.harvestedOn) == Literal(lot.harvested_on, datatype=DATE)
    assert graph.value(node, SL.process) == URIRef(taxonomy.get(lot.process_key).iri)
    assert graph.value(node, SL.code) == Literal(lot.code)


def test_a_decimal_keeps_its_scale(graph: Graph, sample: Dataset) -> None:
    line = sample.order_lines[0]
    node = URIRef(f"{DATA}order-line/{line.order_code}/{line.line_no}")
    amount = graph.value(node, SL.amount)
    assert isinstance(amount, Literal)
    assert amount.datatype == DECIMAL
    assert str(amount) == str(line.amount)
    assert graph.value(node, SL.lineNo) == Literal(line.line_no, datatype=INTEGER)


def test_link_tables_become_one_triple_per_row(graph: Graph, sample: Dataset) -> None:
    assert len(list(graph.subject_objects(SL.harvestedFrom))) == len(sample.lot_farms)
    assert len(list(graph.subject_objects(SL.flavourNote))) == len(sample.product_flavours)


def test_a_flavour_link_points_at_the_concept(graph: Graph, sample: Dataset, taxonomy: Taxonomy) -> None:
    row = sample.product_flavours[0]
    assert (
        URIRef(f"{DATA}product/{row.product_code}"),
        SL.flavourNote,
        URIRef(taxonomy.get(row.flavour_key).iri),
    ) in graph


def test_a_composite_key_gives_a_path(graph: Graph, sample: Dataset) -> None:
    line = sample.order_lines[0]
    node = URIRef(f"{DATA}order-line/{line.order_code}/{line.line_no}")
    assert (node, RDF.type, SL.OrderLine) in graph
    assert graph.value(node, SL.lineOf) == URIRef(f"{DATA}order/{line.order_code}")


def test_a_blend_is_typed_twice_and_has_no_origin_region(graph: Graph, sample: Dataset) -> None:
    blend = next(p for p in sample.products if p.category_key == "category.blend")
    node = URIRef(f"{DATA}product/{blend.code}")
    assert set(graph.objects(node, RDF.type)) == {SL.Product, SL.Blend}
    assert graph.value(node, SL.originRegion) is None


def test_a_one_lot_product_is_a_single_lot_product_with_a_region(graph: Graph, sample: Dataset, taxonomy: Taxonomy) -> None:
    single = next(
        p for p in sample.products if p.category_key in ("category.decaf", "category.single-origin")
    )
    node = URIRef(f"{DATA}product/{single.code}")
    assert set(graph.objects(node, RDF.type)) == {SL.Product, SL.SingleLotProduct}
    assert single.origin_region_key is not None
    assert graph.value(node, SL.originRegion) == URIRef(
        taxonomy.get(single.origin_region_key).iri
    )


def test_a_null_gives_no_triple(graph: Graph, sample: Dataset) -> None:
    assert any(row.valid_until is None for row in sample.certifications)
    for row in sample.certifications:
        node = URIRef(
            f"{DATA}certification/{row.cooperative_code}/{row.certification}/{row.valid_from}"
        )
        assert ((node, SL.validUntil, None) in graph) == (row.valid_until is not None)
    assert all(str(o) != "None" for o in graph.objects() if isinstance(o, Literal))


def test_each_class_table_gives_one_node_per_row(graph: Graph, sample: Dataset) -> None:
    assert len(set(graph.subjects(RDF.type, SL.OrderLine))) == len(sample.order_lines)
    assert len(set(graph.subjects(RDF.type, SL.Product))) == len(sample.products)


def test_a_key_is_percent_encoded(sample: Dataset, taxonomy: Taxonomy, ontology: Ontology, mapping: Mapping) -> None:
    odd = dataclasses.replace(sample.cooperatives[0], code="C 1/x")
    changed = dataclasses.replace(sample, cooperatives=(odd,), lots=(), farms=())
    result = export(changed, taxonomy, ontology, mapping)
    assert (URIRef(f"{DATA}cooperative/C%201%2Fx"), RDF.type, SL.Cooperative) in result


def test_two_exports_hold_the_same_triples(sample: Dataset, taxonomy: Taxonomy, ontology: Ontology, mapping: Mapping, graph: Graph) -> None:
    again = export(sample, taxonomy, ontology, mapping)
    assert set(again) == set(graph)


def test_a_reference_to_a_class_with_a_two_column_key_is_refused(sample: Dataset, taxonomy: Taxonomy, ontology: Ontology, mapping: Mapping) -> None:
    classes = tuple(
        dataclasses.replace(entry, key=("code", "name")) if entry.iri == str(SL.Cooperative) else entry
        for entry in mapping.classes
    )
    with pytest.raises(MappingError, match="Cooperative"):
        export(sample, taxonomy, ontology, Mapping(classes=classes, properties=mapping.properties))


def test_a_link_from_a_class_with_a_two_column_key_is_refused(sample: Dataset, taxonomy: Taxonomy, ontology: Ontology, mapping: Mapping) -> None:
    classes = tuple(
        dataclasses.replace(entry, key=("code", "variety")) if entry.iri == str(SL.Lot) else entry
        for entry in mapping.classes
    )
    with pytest.raises(MappingError, match="Lot"):
        export(sample, taxonomy, ontology, Mapping(classes=classes, properties=mapping.properties))


def test_a_value_that_is_no_concept_key_is_refused_with_its_property_and_column(sample: Dataset, taxonomy: Taxonomy, ontology: Ontology, mapping: Mapping) -> None:
    bad = dataclasses.replace(sample.lots[0], process_key="process.nope")
    changed = dataclasses.replace(sample, lots=(bad,))
    with pytest.raises(MappingError) as raised:
        export(changed, taxonomy, ontology, mapping)
    assert str(raised.value) == (
        f"property {SL.process}: column lot.process_key holds 'process.nope', "
        "which is no concept key"
    )


def test_a_link_value_that_is_no_concept_key_is_refused_with_its_column(sample: Dataset, taxonomy: Taxonomy, ontology: Ontology, mapping: Mapping) -> None:
    bad = dataclasses.replace(sample.product_flavours[0], flavour_key="flavour.nope")
    changed = dataclasses.replace(sample, product_flavours=(bad,))
    with pytest.raises(MappingError, match="column product_flavour.flavour_key holds 'flavour.nope'"):
        export(changed, taxonomy, ontology, mapping)
