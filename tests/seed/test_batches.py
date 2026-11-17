import random
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from itertools import product

from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import planted
from semantic_lab.seed.batches import (
    Batches,
    PlannedBatch,
    finish_batches,
    share_hundredths,
)
from tests.support.seed import (
    CENTS,
    ONE_LOT_CATEGORIES,
    World,
    lot_arrivals,
    lot_countries,
    lot_regions,
    lots_of_batches,
    product_named,
    sold_kg,
)


def test_a_single_origin_batch_has_one_lot_with_share_1(world: World, taxonomy: Taxonomy) -> None:
    supply, sales = world.supply, world.sales
    one_lot = {p.code for p in supply.products if p.category_key in ONE_LOT_CATEGORIES}
    countries = lot_countries(supply, taxonomy)
    lots = lots_of_batches(sales)
    origins: dict[str, set[str]] = defaultdict(set)
    for batch in sales.roast_batches:
        if batch.product_code not in one_lot:
            continue
        assert len(lots[batch.code]) == 1, batch.code
        lot_code, share = lots[batch.code][0]
        assert share == Decimal("1.00"), batch.code
        origins[batch.product_code].add(countries[lot_code])
    assert set(origins) == one_lot
    assert all(len(origin) == 1 for origin in origins.values())


def test_a_one_lot_batch_uses_a_lot_from_its_products_origin_region(world: World) -> None:
    region_of_lot = lot_regions(world.supply)
    origin = {p.code: p.origin_region_key for p in world.supply.products}
    lots = lots_of_batches(world.sales)
    checked = 0
    for batch in world.sales.roast_batches:
        if origin[batch.product_code] is None:
            continue
        checked += 1
        (lot_code, _), = lots[batch.code]
        assert region_of_lot[lot_code] == origin[batch.product_code], batch.code
    assert checked > 1000


def test_a_blend_batch_has_two_to_four_lots_whose_shares_sum_to_exactly_1(world: World) -> None:
    supply, sales = world.supply, world.sales
    blends = {p.code for p in supply.products if p.category_key not in ONE_LOT_CATEGORIES}
    lots = lots_of_batches(sales)
    pools = {
        product_named(supply, "Alba").code: set(planted.ALBA_POOL),
        product_named(supply, "Brisa").code: set(planted.BRISA_POOL),
    }
    count = 0
    for batch in sales.roast_batches:
        if batch.product_code not in blends:
            continue
        count += 1
        links = lots[batch.code]
        codes = [lot for lot, _ in links]
        assert 2 <= len(codes) <= 4, batch.code
        assert len(set(codes)) == len(codes), batch.code
        assert sum(share for _, share in links) == Decimal(1), batch.code
        for _, share in links:
            assert Decimal(0) < share < Decimal(1), batch.code
            assert share == share.quantize(CENTS), batch.code
        if batch.product_code in pools:
            assert set(codes) <= pools[batch.product_code], batch.code
    assert count > 500


def test_a_batch_is_roasted_in_range_and_after_its_lots_arrive(world: World) -> None:
    arrival = lot_arrivals(world.supply)
    lots = lots_of_batches(world.sales)
    for batch in world.sales.roast_batches:
        assert date(2024, 1, 2) <= batch.roasted_on <= date(2025, 12, 28), batch.code
        assert batch.output_kg == batch.output_kg.quantize(CENTS), batch.code
        for lot_code, _ in lots[batch.code]:
            assert arrival[lot_code] < batch.roasted_on, batch.code
    dates = [b.roasted_on for b in world.sales.roast_batches]
    assert dates == sorted(dates)


def test_cost_per_kg_follows_from_the_lots(world: World) -> None:
    price = {lot.code: lot.price_per_kg for lot in world.supply.lots}
    lots = lots_of_batches(world.sales)
    for batch in world.sales.roast_batches:
        raw = sum(share * price[lot] for lot, share in lots[batch.code])
        expected = (raw / Decimal("0.85")).quantize(CENTS, rounding=ROUND_HALF_UP)
        assert batch.cost_per_kg == expected, batch.code


def test_every_product_has_a_batch_by_2024_01_05(world: World) -> None:
    first: dict[str, date] = {}
    for batch in world.sales.roast_batches:
        first.setdefault(batch.product_code, batch.roasted_on)
    assert set(first) == {p.code for p in world.supply.products}
    assert max(first.values()) <= date(2024, 1, 5)


def test_the_recalled_lots_are_used_only_by_their_planned_blend_batches(world: World) -> None:
    sales = world.sales
    lots = lots_of_batches(sales)
    batches = {b.code: b for b in sales.roast_batches}
    blends = {
        p.code
        for p in world.supply.products
        if p.category_key not in ONE_LOT_CATEGORIES and p.name not in planted.BLENDS
    }
    for lot in planted.RECALLED_LOTS:
        consumers = {code for code, links in lots.items() if lot in [item for item, _ in links]}
        assert 3 <= len(consumers) <= 6, lot
        for code in consumers:
            assert batches[code].product_code in blends
            assert batches[code].roasted_on < planted.RECALL_DATES[lot]


def test_alba_and_brisa_share_exactly_three_farms(world: World) -> None:
    supply, sales = world.supply, world.sales
    farms_of_lot: dict[str, set[str]] = defaultdict(set)
    for link in supply.lot_farms:
        farms_of_lot[link.lot_code].add(link.farm_code)
    lots = lots_of_batches(sales)
    product_of = {b.code: b.product_code for b in sales.roast_batches}
    farms: dict[str, set[str]] = defaultdict(set)
    for code, links in lots.items():
        for lot, _ in links:
            farms[product_of[code]] |= farms_of_lot[lot]
    alba = farms[product_named(supply, "Alba").code]
    brisa = farms[product_named(supply, "Brisa").code]
    assert len(alba & brisa) == planted.SHARED_FARMS
    assert len(alba) >= 5
    assert len(brisa) >= 5


def test_no_batch_sells_more_than_its_output(world: World) -> None:
    sold = sold_kg(world.sales)
    assert sold
    for batch in world.sales.roast_batches:
        assert sold.get(batch.code, Decimal(0)) <= batch.output_kg, batch.code


def test_every_batch_has_an_output_of_60_kg_or_more(world: World) -> None:
    for batch in world.sales.roast_batches:
        assert batch.output_kg >= Decimal("60"), batch.code
        assert batch.output_kg == batch.output_kg.quantize(CENTS), batch.code


def test_a_batch_that_sells_little_keeps_its_drawn_size(world: World) -> None:
    sold = sold_kg(world.sales)
    checked = 0
    for batch in world.sales.roast_batches:
        if sold.get(batch.code, Decimal(0)) <= Decimal("50"):
            checked += 1
            assert Decimal("60") <= batch.output_kg <= Decimal("400"), batch.code
    assert checked > 100


def test_a_batch_roasted_above_400_kg_keeps_between_2_and_20_percent_unsold(
    world: World,
) -> None:
    sold = sold_kg(world.sales)
    checked = 0
    for batch in world.sales.roast_batches:
        if batch.output_kg <= Decimal("400"):
            continue
        checked += 1
        kept = sold[batch.code]
        assert kept * Decimal("1.02") <= batch.output_kg, batch.code
        # Rounding the output up to the cent adds less than one cent.
        assert batch.output_kg - CENTS < kept * Decimal("1.20"), batch.code
    assert checked > 100


class FixedUnsoldPercent(random.Random):
    """Draws the lowest value of any range: a size of 60 kg and an unsold percentage of 2."""

    def randint(self, a: int, b: int) -> int:
        return a


def planned(code: str) -> PlannedBatch:
    return PlannedBatch(code, "P-01", date(2024, 1, 2), Decimal("9.50"))


def test_finish_batches_keeps_the_drawn_size_when_it_covers_the_need() -> None:
    batches = Batches((planned("B-0001"),), ())
    (finished,) = finish_batches(batches, {"B-0001": Decimal("10.001")}, FixedUnsoldPercent())
    # The need is 10.001 * 1.02 = 10.21 and the drawn size is 60.00, so the size wins.
    assert finished.output_kg == Decimal("60.00")
    assert finished.product_code == "P-01"
    assert finished.roasted_on == date(2024, 1, 2)
    assert finished.cost_per_kg == Decimal("9.50")


def test_finish_batches_roasts_larger_when_the_need_exceeds_the_drawn_size() -> None:
    batches = Batches((planned("B-0001"), planned("B-0002")), ())
    finished = finish_batches(
        batches,
        {"B-0001": Decimal("100.001"), "B-0002": Decimal("500.000")},
        FixedUnsoldPercent(),
    )
    # 100.001 * 1.02 = 102.00102, which rounds up to 102.01 where nearest would give 102.00.
    assert [(b.code, b.output_kg) for b in finished] == [
        ("B-0001", Decimal("102.01")),
        ("B-0002", Decimal("510.00")),
    ]


def test_finish_batches_never_gives_less_than_60_kg_or_what_was_sold() -> None:
    rng = random.Random(11)
    sales = {
        f"B-{n:04d}": Decimal(rng.randint(1, 5_000_000)) / 1000 for n in range(1, 2001)
    }
    batches = Batches(tuple(planned(code) for code in sales), ())
    finished = finish_batches(batches, sales, rng)
    for batch in finished:
        assert batch.output_kg >= max(Decimal("60"), sales[batch.code] * Decimal("1.02"))
        assert batch.output_kg == batch.output_kg.quantize(CENTS)
    assert any(b.output_kg > Decimal("400") for b in finished)
    assert any(b.output_kg < Decimal("400") for b in finished)


def test_a_batch_with_no_sales_draws_its_output_from_the_range() -> None:
    batches = Batches(tuple(planned(f"B-{n:04d}") for n in range(1, 301)), ())
    finished = finish_batches(batches, {}, random.Random(4))
    assert all(Decimal("60") <= b.output_kg <= Decimal("400") for b in finished)
    assert len({b.output_kg for b in finished}) > 100


def test_the_smallest_share_of_a_blend_is_3_hundredths() -> None:
    # The smallest weight against the largest ones, for the most lots a blend can have:
    # 100 // (1 + 3 * 10) = 3. The first share also takes the rounding remainder, so no share
    # of any weight combination goes below it.
    smallest = 100
    for count in (2, 3, 4):
        for weights in product(range(1, 11), repeat=count):
            hundredths = share_hundredths(list(weights))
            assert sum(hundredths) == 100
            smallest = min(smallest, *hundredths)
    assert smallest == 3
