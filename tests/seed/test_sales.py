import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest

from semantic_lab.domain.records import OrderLine, Product
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import planted
from semantic_lab.seed.sales import Sales, generate_sales
from semantic_lab.seed.supply import Supply, generate_supply

# Planted facts hold for any seed, so every test runs against each of these.
SEEDS = (20261116, 1, 7, 99)
ONE_LOT_CATEGORIES = ("category.single-origin", "category.microlot", "category.decaf")
CENTS = Decimal("0.01")


@dataclass(frozen=True)
class World:
    supply: Supply
    sales: Sales


@pytest.fixture(scope="module", params=SEEDS)
def world(request: pytest.FixtureRequest, taxonomy: Taxonomy) -> World:
    rng = random.Random(request.param)
    supply = generate_supply(taxonomy, rng)
    return World(supply, generate_sales(supply, rng))


def lots_of_batches(sales: Sales) -> dict[str, list[tuple[str, Decimal]]]:
    found: dict[str, list[tuple[str, Decimal]]] = defaultdict(list)
    for link in sales.roast_batch_lots:
        found[link.roast_batch_code].append((link.lot_code, link.share))
    return found


def lot_arrivals(supply: Supply) -> dict[str, date]:
    arrival = {s.code: s.arrived_on for s in supply.shipments}
    return {lot.code: arrival[lot.shipment_code] for lot in supply.lots}


def lot_countries(supply: Supply, taxonomy: Taxonomy) -> dict[str, str]:
    region_of = {c.code: c.region_key for c in supply.cooperatives}
    countries = {}
    for lot in supply.lots:
        parent = taxonomy.get(region_of[lot.cooperative_code]).parent_key
        assert parent is not None
        countries[lot.code] = parent
    return countries


def product_named(supply: Supply, name: str) -> Product:
    return next(p for p in supply.products if p.name == name)


def test_counts_and_codes(world: World) -> None:
    sales = world.sales
    assert len(sales.roast_batches) == 3000
    assert (sales.roast_batches[0].code, sales.roast_batches[-1].code) == ("B-0001", "B-3000")
    assert len(sales.customers) == 300
    assert (sales.customers[0].code, sales.customers[-1].code) == ("K-001", "K-300")
    assert len(sales.orders) == 20000
    assert (sales.orders[0].code, sales.orders[-1].code) == ("O-00001", "O-20000")
    assert len(sales.order_lines) == 60000
    assert [i.code for i in sales.quality_incidents] == ["Q-01", "Q-02"]
    assert len({c.name for c in sales.customers}) == 300
    for customer in sales.customers:
        assert customer.segment in ("cafe", "shop", "restaurant")
        assert customer.country in ("Spain", "Portugal")
        assert customer.city


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
        assert Decimal("60") <= batch.output_kg <= Decimal("400"), batch.code
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


def lines_by_order(sales: Sales) -> dict[str, list[OrderLine]]:
    found: dict[str, list[OrderLine]] = defaultdict(list)
    for line in sales.order_lines:
        found[line.order_code].append(line)
    return found


def test_an_order_has_one_to_six_lines_with_distinct_products(world: World) -> None:
    by_order = lines_by_order(world.sales)
    assert set(by_order) == {o.code for o in world.sales.orders}
    customers = {c.code for c in world.sales.customers}
    for order in world.sales.orders:
        lines = by_order[order.code]
        assert 1 <= len(lines) <= 6, order.code
        assert [line.line_no for line in lines] == list(range(1, len(lines) + 1)), order.code
        assert len({line.product_code for line in lines}) == len(lines), order.code
        assert order.customer_code in customers
    assert len({o.customer_code for o in world.sales.orders}) == 300


def test_a_line_is_filled_from_a_batch_of_its_product_roasted_on_or_before_the_order(
    world: World,
) -> None:
    batches = {b.code: b for b in world.sales.roast_batches}
    ordered_on = {o.code: o.ordered_on for o in world.sales.orders}
    for line in world.sales.order_lines:
        batch = batches[line.roast_batch_code]
        assert batch.product_code == line.product_code, (line.order_code, line.line_no)
        assert batch.roasted_on <= ordered_on[line.order_code], (line.order_code, line.line_no)


def test_line_arithmetic(world: World) -> None:
    products = {p.code: p for p in world.supply.products}
    for line in world.sales.order_lines:
        product = products[line.product_code]
        assert 1 <= line.bags <= 40
        assert line.unit_price == product.list_price
        assert line.amount == line.bags * line.unit_price
        assert line.amount == line.amount.quantize(CENTS)
        assert line.kg == (Decimal(line.bags * product.bag_weight_g) / 1000).quantize(
            Decimal("0.001")
        )


def test_orders_are_dated_2024_01_02_to_2025_12_31_and_every_month_has_orders(
    world: World,
) -> None:
    dates = [o.ordered_on for o in world.sales.orders]
    assert dates == sorted(dates)
    assert date(2024, 1, 2) <= dates[0]
    assert dates[-1] <= date(2025, 12, 31)
    months = {(d.year, d.month) for d in dates}
    assert months == {(year, month) for year in (2024, 2025) for month in range(1, 13)}


def test_each_recalled_lot_reaches_customers(world: World) -> None:
    sales = world.sales
    lots = lots_of_batches(sales)
    batches = {b.code: b for b in sales.roast_batches}
    customer_of = {o.code: o.customer_code for o in sales.orders}
    blends = {
        p.code
        for p in world.supply.products
        if p.category_key not in ONE_LOT_CATEGORIES and p.name not in planted.BLENDS
    }
    assert [i.lot_code for i in sales.quality_incidents] == list(planted.RECALLED_LOTS)
    for incident in sales.quality_incidents:
        assert incident.kind == "recall"
        assert incident.reported_on == planted.RECALL_DATES[incident.lot_code]
        assert incident.description
        consumers = {
            code for code, links in lots.items() if incident.lot_code in [lot for lot, _ in links]
        }
        assert 3 <= len(consumers) <= 6, incident.lot_code
        for code in consumers:
            assert batches[code].product_code in blends
            assert batches[code].roasted_on < incident.reported_on
        reached = {
            customer_of[line.order_code]
            for line in sales.order_lines
            if line.roast_batch_code in consumers
        }
        assert 10 <= len(reached) <= 40, incident.lot_code


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
