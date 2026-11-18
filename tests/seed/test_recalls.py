from semantic_lab.seed import planted
from tests.support.seed import World, lots_of_batches


def test_each_recalled_lot_reaches_between_10_and_40_customers(world: World) -> None:
    sales = world.sales
    lots = lots_of_batches(sales)
    customer_of = {o.code: o.customer_code for o in sales.orders}
    for lot in planted.RECALLED_LOTS:
        consumers = {code for code, links in lots.items() if lot in [item for item, _ in links]}
        reached = {
            customer_of[line.order_code]
            for line in sales.order_lines
            if line.roast_batch_code in consumers
        }
        assert 10 <= len(reached) <= 40, lot


def test_a_recalled_lots_lines_are_ordered_between_the_roasting_and_the_recall(
    world: World,
) -> None:
    sales = world.sales
    lots = lots_of_batches(sales)
    batches = {b.code: b for b in sales.roast_batches}
    ordered_on = {o.code: o.ordered_on for o in sales.orders}
    for lot in planted.RECALLED_LOTS:
        consumers = {code for code, links in lots.items() if lot in [item for item, _ in links]}
        lines = [line for line in sales.order_lines if line.roast_batch_code in consumers]
        assert lines, lot
        for line in lines:
            assert batches[line.roast_batch_code].roasted_on <= ordered_on[line.order_code]
            assert ordered_on[line.order_code] <= planted.RECALL_DATES[lot]
