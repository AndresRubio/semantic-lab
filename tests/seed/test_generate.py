import dataclasses

import pytest

from semantic_lab.domain.errors import GenerationError
from semantic_lab.domain.records import Dataset
from semantic_lab.domain.taxonomy import Concept, Taxonomy, build_taxonomy
from semantic_lab.seed import generate

PINNED = "79bcee403c3717d5f1c726363ffa73d3a76f74c3322a92397375816d3724a143"


def test_every_reference_resolves(dataset: Dataset, taxonomy: Taxonomy) -> None:
    concepts = {c.key for c in taxonomy.concepts}
    cooperatives = {c.code for c in dataset.cooperatives}
    farms = {f.code for f in dataset.farms}
    shipments = {s.code for s in dataset.shipments}
    lots = {lot.code for lot in dataset.lots}
    products = {p.code for p in dataset.products}
    batches = {b.code for b in dataset.roast_batches}
    customers = {c.code for c in dataset.customers}
    orders = {o.code for o in dataset.orders}
    assert {c.region_key for c in dataset.cooperatives} <= concepts
    assert {c.cooperative_code for c in dataset.certifications} <= cooperatives
    assert {f.cooperative_code for f in dataset.farms} <= cooperatives
    assert {lot.cooperative_code for lot in dataset.lots} <= cooperatives
    assert {lot.shipment_code for lot in dataset.lots} <= shipments
    assert {lot.process_key for lot in dataset.lots} <= concepts
    assert {link.lot_code for link in dataset.lot_farms} <= lots
    assert {link.farm_code for link in dataset.lot_farms} <= farms
    assert {p.category_key for p in dataset.products} <= concepts
    assert {p.origin_region_key for p in dataset.products} - {None} <= concepts
    assert {link.product_code for link in dataset.product_flavours} <= products
    assert {link.flavour_key for link in dataset.product_flavours} <= concepts
    assert {b.product_code for b in dataset.roast_batches} <= products
    assert {link.roast_batch_code for link in dataset.roast_batch_lots} <= batches
    assert {link.lot_code for link in dataset.roast_batch_lots} <= lots
    assert {o.customer_code for o in dataset.orders} <= customers
    assert {line.order_code for line in dataset.order_lines} <= orders
    assert {line.product_code for line in dataset.order_lines} <= products
    assert {line.roast_batch_code for line in dataset.order_lines} <= batches
    assert {i.lot_code for i in dataset.quality_incidents} <= lots
    for table in dataclasses.fields(dataset):
        assert getattr(dataset, table.name), table.name


def test_same_seed_same_digest(dataset: Dataset, taxonomy: Taxonomy) -> None:
    again = generate.generate(taxonomy, generate.DEFAULT_SEED)
    assert again == dataset
    assert generate.digest(again) == generate.digest(dataset)
    assert len(generate.digest(dataset)) == 64


def test_another_seed_another_digest(dataset: Dataset, taxonomy: Taxonomy) -> None:
    other = generate.generate(taxonomy, generate.DEFAULT_SEED + 1)
    assert generate.digest(other) != generate.digest(dataset)


def test_the_default_digest_is_pinned(dataset: Dataset) -> None:
    assert generate.digest(dataset) == PINNED


def test_a_taxonomy_the_generator_cannot_build_from_is_refused_before_any_draw(
    taxonomy: Taxonomy,
) -> None:
    extra = Concept(
        "process.carbonic-maceration",
        "process",
        "https://example.org/process/carbonic-maceration",
        "Carbonic maceration",
        "Maceracion carbonica",
        (),
        None,
    )
    with pytest.raises(GenerationError, match=r"process\.carbonic-maceration"):
        generate.generate(build_taxonomy([*taxonomy.concepts, extra]), generate.DEFAULT_SEED)
