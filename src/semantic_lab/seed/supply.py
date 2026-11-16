"""The supply side of the seed: cooperatives, farms, shipments, lots and the product range.

Everything here is a pure function of the taxonomy and the random generator passed in. This
module builds the cooperatives, certifications, farms and shipments, and `lots` and `products`
build the rest.
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta

from semantic_lab.domain.errors import GenerationError
from semantic_lab.domain.records import (
    Cooperative,
    CooperativeCertification,
    Farm,
    Lot,
    LotFarm,
    Product,
    ProductFlavour,
    Shipment,
)
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import planted
from semantic_lab.seed.draw import random_date
from semantic_lab.seed.lots import EARLY_SHIPMENTS_PER_COUNTRY, World, generate_lots
from semantic_lab.seed.names import (
    COOPERATIVE_NAMES,
    DESTINATION_PORTS,
    FARM_PLACES,
    FARM_PREFIXES,
    ORIGIN_PORTS,
)
from semantic_lab.seed.products import generate_products

# Lots arrived by this day can be roasted from the first roasting days on.
EARLY_ARRIVAL_END = date(2023, 12, 31)
SHIPMENT_COUNT = 80
FARMS_PER_COOPERATIVE = 8
EARLY_DEPARTURE = (date(2023, 10, 20), date(2023, 11, 15))
LATER_DEPARTURE = (date(2023, 12, 10), date(2025, 10, 31))
DEPARTURE_JITTER_DAYS = 8
SAILING_DAYS = (20, 45)

LAPSED_ORGANIC_FROM = date(2022, 1, 1)
OTHER_ORGANIC_COOPERATIVES = 6
OTHER_ORGANIC_FROM = (date(2019, 1, 1), date(2022, 12, 31))
FAIR_TRADE_COOPERATIVES = 5
FAIR_TRADE_FROM = (date(2018, 1, 1), date(2023, 6, 30))


@dataclass(frozen=True)
class Supply:
    cooperatives: tuple[Cooperative, ...]
    certifications: tuple[CooperativeCertification, ...]
    farms: tuple[Farm, ...]
    shipments: tuple[Shipment, ...]
    lots: tuple[Lot, ...]
    lot_farms: tuple[LotFarm, ...]
    products: tuple[Product, ...]
    product_flavours: tuple[ProductFlavour, ...]


def generate_supply(taxonomy: Taxonomy, rng: random.Random) -> Supply:
    countries = _countries(taxonomy)
    cooperatives = _cooperatives(taxonomy, countries, rng)
    certifications = _certifications(cooperatives, rng)
    farms = _farms(cooperatives, rng)
    shipments, country_of_shipment = _shipments(countries, rng)
    world = World(
        cooperatives_by_country={
            country: tuple(c for c in cooperatives if _country_of(taxonomy, c.region_key) == country)
            for country in countries
        },
        farms_by_cooperative={
            c.code: tuple(f.code for f in farms if f.cooperative_code == c.code)
            for c in cooperatives
        },
        shipments=shipments,
        shipments_by_country={
            country: tuple(s for s in shipments if country_of_shipment[s.code] == country)
            for country in countries
        },
        country_of_shipment=country_of_shipment,
    )
    lots, lot_farms = generate_lots(taxonomy, world, cooperatives, rng)
    origin_regions = _origin_regions(cooperatives, shipments, lots)
    products, product_flavours = generate_products(taxonomy, rng, origin_regions)
    return Supply(
        cooperatives=cooperatives,
        certifications=certifications,
        farms=farms,
        shipments=shipments,
        lots=lots,
        lot_farms=lot_farms,
        products=products,
        product_flavours=product_flavours,
    )


def _origin_regions(
    cooperatives: tuple[Cooperative, ...],
    shipments: tuple[Shipment, ...],
    lots: tuple[Lot, ...],
) -> tuple[str, ...]:
    """The regions a one-lot product may come from: those with a lot that can be roasted at once.

    A recalled lot does not count, because only its own batches may consume it.
    """
    region_of = {c.code: c.region_key for c in cooperatives}
    arrived_on = {s.code: s.arrived_on for s in shipments}
    return tuple(
        sorted(
            {
                region_of[lot.cooperative_code]
                for lot in lots
                if arrived_on[lot.shipment_code] <= EARLY_ARRIVAL_END
                and lot.code not in planted.RECALLED_LOTS
            }
        )
    )


def _country_of(taxonomy: Taxonomy, region_key: str) -> str:
    parent = taxonomy.get(region_key).parent_key
    if parent is None:
        raise GenerationError(f"region {region_key} has no country")
    return parent


def _countries(taxonomy: Taxonomy) -> tuple[str, ...]:
    return tuple(sorted({_country_of(taxonomy, r.key) for r in taxonomy.leaves("geo")}))


def _cooperatives(
    taxonomy: Taxonomy, countries: tuple[str, ...], rng: random.Random
) -> tuple[Cooperative, ...]:
    names = list(COOPERATIVE_NAMES)
    rng.shuffle(names)
    rows = []
    for index, name in enumerate(names):
        regions = taxonomy.children(countries[index % len(countries)])
        region = regions[(index // len(countries)) % len(regions)]
        rows.append(Cooperative(f"C-{index + 1:02d}", name, region.key))
    return tuple(rows)


def _certifications(
    cooperatives: tuple[Cooperative, ...], rng: random.Random
) -> tuple[CooperativeCertification, ...]:
    codes = [c.code for c in cooperatives]
    others = [code for code in codes if code != planted.LAPSED_COOPERATIVE]
    rows = [
        CooperativeCertification(
            planted.LAPSED_COOPERATIVE, "organic", LAPSED_ORGANIC_FROM, planted.LAPSE_DATE
        )
    ]
    for code in sorted(rng.sample(others, OTHER_ORGANIC_COOPERATIVES)):
        rows.append(
            CooperativeCertification(code, "organic", random_date(rng, *OTHER_ORGANIC_FROM), None)
        )
    for code in sorted(rng.sample(codes, FAIR_TRADE_COOPERATIVES)):
        rows.append(
            CooperativeCertification(code, "fair_trade", random_date(rng, *FAIR_TRADE_FROM), None)
        )
    return tuple(sorted(rows, key=lambda r: (r.cooperative_code, r.certification, r.valid_from)))


def _farms(cooperatives: tuple[Cooperative, ...], rng: random.Random) -> tuple[Farm, ...]:
    rows = []
    for cooperative_index, cooperative in enumerate(cooperatives):
        for slot in range(FARMS_PER_COOPERATIVE):
            number = cooperative_index * FARMS_PER_COOPERATIVE + slot + 1
            name = f"{rng.choice(FARM_PREFIXES)} {rng.choice(FARM_PLACES)}"
            rows.append(Farm(f"F-{number:03d}", name, cooperative.code, rng.randint(900, 2200)))
    return tuple(rows)


def _shipments(
    countries: tuple[str, ...], rng: random.Random
) -> tuple[tuple[Shipment, ...], dict[str, str]]:
    planned: list[tuple[date, str, date]] = []
    for position, country in enumerate(countries):
        count = SHIPMENT_COUNT // len(countries) + (
            1 if position < SHIPMENT_COUNT % len(countries) else 0
        )
        departures = [
            random_date(rng, *EARLY_DEPARTURE) for _ in range(EARLY_SHIPMENTS_PER_COUNTRY)
        ]
        later = count - EARLY_SHIPMENTS_PER_COUNTRY
        first, last = LATER_DEPARTURE
        span = (last - first).days
        for step in range(later):
            base = first + timedelta(days=span * step // (later - 1))
            jittered = base + timedelta(
                days=rng.randint(-DEPARTURE_JITTER_DAYS, DEPARTURE_JITTER_DAYS)
            )
            departures.append(min(max(jittered, first), last))
        for departed_on in departures:
            arrived_on = departed_on + timedelta(days=rng.randint(*SAILING_DAYS))
            planned.append((departed_on, country, arrived_on))
    planned.sort()
    shipments = []
    country_of_shipment = {}
    for index, (departed_on, country, arrived_on) in enumerate(planned):
        code = f"S-{index + 1:02d}"
        destination = rng.choice(DESTINATION_PORTS)
        shipments.append(Shipment(code, ORIGIN_PORTS[country], destination, departed_on, arrived_on))
        country_of_shipment[code] = country
    return tuple(shipments), country_of_shipment
