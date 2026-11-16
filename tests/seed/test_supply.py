import random
from collections import Counter, defaultdict
from datetime import date

from semantic_lab.domain.records import Lot
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import planted
from semantic_lab.seed.supply import Supply, generate_supply
from tests.support.seed import lot_countries


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
    per_country = Counter(
        taxonomy.get(c.region_key).parent_key for c in supply.cooperatives
    )
    regions = taxonomy.leaves("geo")
    assert len(per_country) == len({r.parent_key for r in regions}) == 6
    assert min(per_country.values()) >= 2
    assert {c.region_key for c in supply.cooperatives} <= {r.key for r in regions}


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


def test_the_lapsed_cooperatives_certificates(supply: Supply) -> None:
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


def test_same_seed_same_supply_and_another_seed_differs(taxonomy: Taxonomy) -> None:
    first = generate_supply(taxonomy, random.Random(5))
    assert first == generate_supply(taxonomy, random.Random(5))
    assert first != generate_supply(taxonomy, random.Random(6))
