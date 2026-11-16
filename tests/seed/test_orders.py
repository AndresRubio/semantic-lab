from datetime import date
from decimal import Decimal

from tests.support.seed import CENTS, World, lines_by_order


def test_customers_are_iberian_organisations_with_unique_names(world: World) -> None:
    customers = world.sales.customers
    assert len(customers) == 300
    assert (customers[0].code, customers[-1].code) == ("K-001", "K-300")
    assert len({c.name for c in customers}) == 300
    for customer in customers:
        assert customer.segment in ("cafe", "shop", "restaurant")
        assert customer.country in ("Spain", "Portugal")
        assert customer.city


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
