from semantic_lab.seed import planted
from tests.support.seed import World


def test_counts_and_codes(world: World) -> None:
    sales = world.sales
    assert len(sales.roast_batches) == 3000
    assert (sales.roast_batches[0].code, sales.roast_batches[-1].code) == ("B-0001", "B-3000")
    assert len(sales.customers) == 300
    assert len(sales.orders) == 20000
    assert (sales.orders[0].code, sales.orders[-1].code) == ("O-00001", "O-20000")
    assert len(sales.order_lines) == 60000
    assert [i.code for i in sales.quality_incidents] == ["Q-01", "Q-02"]


def test_the_incidents_are_the_recalls_on_the_planted_dates(world: World) -> None:
    incidents = world.sales.quality_incidents
    assert [i.lot_code for i in incidents] == list(planted.RECALLED_LOTS)
    for incident in incidents:
        assert incident.kind == "recall"
        assert incident.reported_on == planted.RECALL_DATES[incident.lot_code]
        assert incident.description
