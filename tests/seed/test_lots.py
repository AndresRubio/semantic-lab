from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import planted
from semantic_lab.seed.supply import Supply
from tests.support.seed import EARLY_END, lot_arrivals, lot_countries


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


def test_enough_lots_arrive_before_roasting_starts(supply: Supply, taxonomy: Taxonomy) -> None:
    arrival = lot_arrivals(supply)
    countries = lot_countries(supply, taxonomy)
    early = [lot for lot in supply.lots if arrival[lot.code] <= EARLY_END]
    assert len(early) >= 60
    assert {countries[lot.code] for lot in early} == set(countries.values())


def test_the_blend_pools(supply: Supply) -> None:
    assert len(planted.ALBA_POOL) == len(planted.BRISA_POOL) == 12
    assert not set(planted.ALBA_POOL) & set(planted.BRISA_POOL)
    farms_of: dict[str, set[str]] = defaultdict(set)
    for link in supply.lot_farms:
        farms_of[link.lot_code].add(link.farm_code)
    arrival = lot_arrivals(supply)
    pool_farms = []
    for pool in (planted.ALBA_POOL, planted.BRISA_POOL):
        assert set(pool) <= set(arrival)
        farms = set().union(*(farms_of[code] for code in pool))
        assert len(farms) >= 5
        pool_farms.append(farms)
        early = [code for code in pool if arrival[code] <= EARLY_END]
        assert len(early) >= 4
    assert len(pool_farms[0] & pool_farms[1]) == planted.SHARED_FARMS


def test_a_recalled_lot_arrives_60_days_or_more_before_its_recall(supply: Supply) -> None:
    arrival = lot_arrivals(supply)
    for code in planted.RECALLED_LOTS:
        assert arrival[code] <= planted.RECALL_DATES[code] - timedelta(days=60)


def test_the_recalled_lots_exist(supply: Supply) -> None:
    codes = {lot.code for lot in supply.lots}
    assert set(planted.RECALLED_LOTS) <= codes
    assert set(planted.RECALL_DATES) == set(planted.RECALLED_LOTS)


def test_the_lapsed_cooperative_harvests_before_and_after_its_certificate_ends(
    supply: Supply,
) -> None:
    harvests = [
        lot.harvested_on
        for lot in supply.lots
        if lot.cooperative_code == planted.LAPSED_COOPERATIVE
    ]
    before = [h for h in harvests if date(2025, 1, 1) <= h <= planted.LAPSE_DATE]
    after = [h for h in harvests if h > planted.LAPSE_DATE]
    assert len(before) >= 5
    assert len(after) >= 5
