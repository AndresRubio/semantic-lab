from collections import Counter, defaultdict
from decimal import Decimal

from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import planted
from semantic_lab.seed.supply import Supply
from tests.support.seed import (
    BLEND_CATEGORIES,
    EARLY_END,
    ONE_LOT_CATEGORIES,
    lot_arrivals,
    lot_regions,
)


def test_the_range_has_28_single_origin_and_microlot_10_blends_and_2_decafs(
    supply: Supply, taxonomy: Taxonomy
) -> None:
    categories = {c.key for c in taxonomy.in_scheme("category")} - {"category.coffee"}
    assert {p.category_key for p in supply.products} <= categories
    by_category = Counter(p.category_key for p in supply.products)
    origin = by_category["category.single-origin"] + by_category["category.microlot"]
    blend = sum(by_category[key] for key in BLEND_CATEGORIES)
    assert (origin, blend, by_category["category.decaf"]) == (28, 10, 2)
    assert len({p.name for p in supply.products}) == 40
    blend_names = {p.name for p in supply.products if p.category_key in BLEND_CATEGORIES}
    assert set(planted.BLENDS) <= blend_names


def test_a_product_has_one_to_three_flavour_notes(supply: Supply, taxonomy: Taxonomy) -> None:
    flavour_leaves = {c.key for c in taxonomy.leaves("flavour")}
    notes: dict[str, list[str]] = defaultdict(list)
    for link in supply.product_flavours:
        notes[link.product_code].append(link.flavour_key)
    assert len(supply.product_flavours) == len(set(supply.product_flavours))
    for product in supply.products:
        assert 1 <= len(notes[product.code]) <= 3, product.code
        assert set(notes[product.code]) <= flavour_leaves, product.code


def test_a_product_has_a_bag_weight_and_a_price_in_cents(supply: Supply) -> None:
    for product in supply.products:
        assert product.bag_weight_g in (250, 1000)
        assert product.list_price > 0
        assert product.list_price == product.list_price.quantize(Decimal("0.01"))


def test_a_one_lot_product_has_an_origin_region_and_a_blend_has_none(
    supply: Supply, taxonomy: Taxonomy
) -> None:
    leaves = {c.key for c in taxonomy.leaves("geo")}
    for product in supply.products:
        if product.category_key in ONE_LOT_CATEGORIES:
            assert product.origin_region_key in leaves, product.code
        else:
            assert product.category_key in BLEND_CATEGORIES, product.code
            assert product.origin_region_key is None, product.code


def test_a_one_lot_products_name_starts_with_its_regions_english_label(
    supply: Supply, taxonomy: Taxonomy
) -> None:
    for product in supply.products:
        if product.origin_region_key is not None:
            label = taxonomy.get(product.origin_region_key).label_en
            assert product.name.startswith(f"{label} "), product.code


def test_an_origin_region_has_a_lot_that_arrived_by_2023_12_31(supply: Supply) -> None:
    arrival = lot_arrivals(supply)
    region = lot_regions(supply)
    early = {
        region[lot.code]
        for lot in supply.lots
        if arrival[lot.code] <= EARLY_END and lot.code not in planted.RECALLED_LOTS
    }
    for product in supply.products:
        if product.origin_region_key is not None:
            assert product.origin_region_key in early, product.code
