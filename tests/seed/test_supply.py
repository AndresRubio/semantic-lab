import random
from collections import Counter, defaultdict
from datetime import date, timedelta
from decimal import Decimal

import pytest

from semantic_lab.domain.records import Lot
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import planted
from semantic_lab.seed.supply import Supply, generate_supply

# Planted facts hold for any seed, so every test runs against each of these.
SEEDS = (20261116, 1, 7, 99)
EARLY_END = date(2023, 12, 31)
BLEND_KEYS = ("category.blend", "category.espresso-blend", "category.filter-blend")


@pytest.fixture(scope="module", params=SEEDS)
def supply(request: pytest.FixtureRequest, taxonomy: Taxonomy) -> Supply:
    return generate_supply(taxonomy, random.Random(request.param))


def country_of_region(taxonomy: Taxonomy, region_key: str) -> str:
    parent = taxonomy.get(region_key).parent_key
    assert parent is not None
    return parent


def lot_countries(supply: Supply, taxonomy: Taxonomy) -> dict[str, str]:
    region_of = {c.code: c.region_key for c in supply.cooperatives}
    return {
        lot.code: country_of_region(taxonomy, region_of[lot.cooperative_code])
        for lot in supply.lots
    }


def arrival_of(supply: Supply) -> dict[str, date]:
    return {s.code: s.arrived_on for s in supply.shipments}


def test_counts_and_codes(supply: Supply) -> None:
    assert len(supply.cooperatives) == 15
    assert (supply.cooperatives[0].code, supply.cooperatives[-1].code) == ("C-01", "C-15")
    assert len(supply.farms) == 120
    assert (supply.farms[0].code, supply.farms[-1].code) == ("F-001", "F-120")
    assert len(supply.shipments) == 80
    assert (supply.shipments[0].code, supply.shipments[-1].code) == ("S-01", "S-80")
    assert len(supply.lots) == 600
    assert (supply.lots[0].code, supply.lots[-1].code) == ("L-0001", "L-0600")
    assert len(supply.products) == 40
    assert (supply.products[0].code, supply.products[-1].code) == ("P-01", "P-40")
    farms_per_cooperative = Counter(f.cooperative_code for f in supply.farms)
    assert set(farms_per_cooperative.values()) == {8}
    assert len(farms_per_cooperative) == 15


def test_every_country_has_two_cooperatives_or_more(
    supply: Supply, taxonomy: Taxonomy
) -> None:
    per_country = Counter(country_of_region(taxonomy, c.region_key) for c in supply.cooperatives)
    regions = taxonomy.leaves("geo")
    assert len(per_country) == len({r.parent_key for r in regions}) == 6
    assert min(per_country.values()) >= 2
    assert {c.region_key for c in supply.cooperatives} <= {r.key for r in regions}


def test_a_lot_has_one_to_three_farms_all_from_its_cooperative(supply: Supply) -> None:
    farm_cooperative = {f.code: f.cooperative_code for f in supply.farms}
    farms_of: dict[str, list[str]] = defaultdict(list)
    for link in supply.lot_farms:
        farms_of[link.lot_code].append(link.farm_code)
    assert len(supply.lot_farms) == len(set(supply.lot_farms))
    for lot in supply.lots:
        farms = farms_of[lot.code]
        assert 1 <= len(farms) <= 3, lot.code
        assert {farm_cooperative[f] for f in farms} == {lot.cooperative_code}, lot.code


def test_lot_values_are_in_range(supply: Supply, taxonomy: Taxonomy) -> None:
    processes = {c.key for c in taxonomy.in_scheme("process")}
    cents = Decimal("0.01")
    for lot in supply.lots:
        assert date(2023, 10, 1) <= lot.harvested_on <= date(2025, 9, 30), lot.code
        assert Decimal("600") <= lot.weight_kg <= Decimal("3000"), lot.code
        assert Decimal("4.00") <= lot.price_per_kg <= Decimal("14.00"), lot.code
        assert lot.weight_kg == lot.weight_kg.quantize(cents), lot.code
        assert lot.price_per_kg == lot.price_per_kg.quantize(cents), lot.code
        assert lot.process_key in processes, lot.code
        assert lot.variety


def test_a_shipment_carries_lots_of_one_country_and_sails_after_their_harvest(
    supply: Supply, taxonomy: Taxonomy
) -> None:
    countries = lot_countries(supply, taxonomy)
    lots_of: dict[str, list[Lot]] = defaultdict(list)
    for lot in supply.lots:
        lots_of[lot.shipment_code].append(lot)
    ports: dict[str, set[str]] = defaultdict(set)
    for shipment in supply.shipments:
        lots = lots_of[shipment.code]
        assert lots, shipment.code
        assert len({countries[lot.code] for lot in lots}) == 1, shipment.code
        ports[countries[lots[0].code]].add(shipment.origin_port)
        assert all(shipment.departed_on > lot.harvested_on for lot in lots), shipment.code
        sailing_days = (shipment.arrived_on - shipment.departed_on).days
        assert 20 <= sailing_days <= 45, shipment.code
    assert all(len(origin) == 1 for origin in ports.values())
    assert len(ports) == 6
    assert len({next(iter(origin)) for origin in ports.values()}) == 6


def test_products(supply: Supply, taxonomy: Taxonomy) -> None:
    categories = {c.key for c in taxonomy.in_scheme("category")} - {"category.coffee"}
    assert {p.category_key for p in supply.products} <= categories
    by_category = Counter(p.category_key for p in supply.products)
    origin = by_category["category.single-origin"] + by_category["category.microlot"]
    blend = sum(by_category[key] for key in BLEND_KEYS)
    assert (origin, blend, by_category["category.decaf"]) == (28, 10, 2)
    assert len({p.name for p in supply.products}) == 40
    blend_names = {p.name for p in supply.products if p.category_key in BLEND_KEYS}
    assert set(planted.BLENDS) <= blend_names
    flavour_leaves = {c.key for c in taxonomy.leaves("flavour")}
    notes: dict[str, list[str]] = defaultdict(list)
    for link in supply.product_flavours:
        notes[link.product_code].append(link.flavour_key)
    assert len(supply.product_flavours) == len(set(supply.product_flavours))
    for product in supply.products:
        assert 1 <= len(notes[product.code]) <= 3, product.code
        assert set(notes[product.code]) <= flavour_leaves, product.code
        assert product.bag_weight_g in (250, 1000)
        assert product.list_price > 0
        assert product.list_price == product.list_price.quantize(Decimal("0.01"))


def test_enough_lots_arrive_before_roasting_starts(supply: Supply, taxonomy: Taxonomy) -> None:
    arrival = arrival_of(supply)
    countries = lot_countries(supply, taxonomy)
    early = [lot for lot in supply.lots if arrival[lot.shipment_code] <= EARLY_END]
    assert len(early) >= 60
    assert {countries[lot.code] for lot in early} == set(countries.values())


def test_the_blend_pools(supply: Supply) -> None:
    assert len(planted.ALBA_POOL) == len(planted.BRISA_POOL) == 12
    assert not set(planted.ALBA_POOL) & set(planted.BRISA_POOL)
    farms_of: dict[str, set[str]] = defaultdict(set)
    for link in supply.lot_farms:
        farms_of[link.lot_code].add(link.farm_code)
    arrival = arrival_of(supply)
    shipment_of = {lot.code: lot.shipment_code for lot in supply.lots}
    pool_farms = []
    for pool in (planted.ALBA_POOL, planted.BRISA_POOL):
        assert set(pool) <= set(shipment_of)
        farms = set().union(*(farms_of[code] for code in pool))
        assert len(farms) >= 5
        pool_farms.append(farms)
        early = [code for code in pool if arrival[shipment_of[code]] <= EARLY_END]
        assert len(early) >= 4
    assert len(pool_farms[0] & pool_farms[1]) == planted.SHARED_FARMS


def test_a_recalled_lot_arrives_60_days_or_more_before_its_recall(supply: Supply) -> None:
    arrival = arrival_of(supply)
    shipment_of = {lot.code: lot.shipment_code for lot in supply.lots}
    for code in planted.RECALLED_LOTS:
        assert arrival[shipment_of[code]] <= planted.RECALL_DATES[code] - timedelta(days=60)


def test_the_lapsed_cooperative(supply: Supply) -> None:
    organic = [c for c in supply.certifications if c.certification == "organic"]
    lapsed = [c for c in organic if c.cooperative_code == planted.LAPSED_COOPERATIVE]
    assert [(c.valid_from, c.valid_until) for c in lapsed] == [
        (date(2022, 1, 1), planted.LAPSE_DATE)
    ]
    others = [c for c in organic if c.cooperative_code != planted.LAPSED_COOPERATIVE]
    assert len(others) == 6
    assert len({c.cooperative_code for c in others}) == 6
    assert all(c.valid_until is None for c in others)
    assert {c.certification for c in supply.certifications} == {"organic", "fair_trade"}
    harvests = [
        lot.harvested_on
        for lot in supply.lots
        if lot.cooperative_code == planted.LAPSED_COOPERATIVE
    ]
    before = [h for h in harvests if date(2025, 1, 1) <= h <= planted.LAPSE_DATE]
    after = [h for h in harvests if h > planted.LAPSE_DATE]
    assert len(before) >= 5
    assert len(after) >= 5


def test_the_recalled_lots_exist(supply: Supply) -> None:
    codes = {lot.code for lot in supply.lots}
    assert set(planted.RECALLED_LOTS) <= codes
    assert set(planted.RECALL_DATES) == set(planted.RECALLED_LOTS)


def test_same_seed_same_supply_and_another_seed_differs(taxonomy: Taxonomy) -> None:
    first = generate_supply(taxonomy, random.Random(5))
    assert first == generate_supply(taxonomy, random.Random(5))
    assert first != generate_supply(taxonomy, random.Random(6))
