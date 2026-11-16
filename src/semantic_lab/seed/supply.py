"""The supply side of the seed: cooperatives, farms, shipments, lots and the product range.

Everything here is a pure function of the taxonomy and the random generator passed in. The
facts in `planted` hold by construction, so they hold for every seed: the pool lots, the
recalled lots and the lapsed cooperative's lots are placed first, and the ordinary lots fill
the rest.
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

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

HARVEST_START = date(2023, 10, 1)
HARVEST_END = date(2025, 9, 30)
EARLY_ARRIVAL_END = date(2023, 12, 31)

LOT_COUNT = 600
SHIPMENT_COUNT = 80
FARMS_PER_COOPERATIVE = 8
MIN_LOTS_PER_SHIPMENT = 6
EARLY_SHIPMENTS_PER_COUNTRY = 2
EARLY_DEPARTURE = (date(2023, 10, 20), date(2023, 11, 15))
LATER_DEPARTURE = (date(2023, 12, 10), date(2025, 10, 31))
DEPARTURE_JITTER_DAYS = 8
SAILING_DAYS = (20, 45)
# A lot is harvested this many days before its shipment sails, at the earliest and the latest.
HARVEST_LEAD_DAYS = (5, 45)

POOL_COUNTRY_INDEX = 1
POOL_SIZE = 12
POOL_ONLY_FARMS = 3
POOL_LOTS_ON_EARLY_SHIPMENTS = 6
LAPSED_LOTS_PER_SIDE = 6
RECALL_LEAD_DAYS = 60
OTHER_ORGANIC_COOPERATIVES = 6
FAIR_TRADE_COOPERATIVES = 5

SINGLE_ORIGIN_PRODUCTS = 28
BLEND_PRODUCTS = 10
DECAF_PRODUCTS = 2

COOPERATIVE_NAMES = (
    "Altos del Sol",
    "Rio Claro Growers",
    "Cumbre Verde",
    "Bosque Nublado",
    "Valle Hondo",
    "Tierra Fina",
    "La Esperanza Collective",
    "Montana Dorada",
    "Sol Naciente",
    "Piedra Blanca",
    "Aguas Claras",
    "Cerro Alto",
    "Monte Sereno",
    "Campo Real",
    "Nube Roja",
)
FARM_PREFIXES = ("Finca", "Hacienda", "Parcela", "Rancho")
FARM_PLACES = (
    "El Mirador",
    "La Loma",
    "Los Pinos",
    "San Rafael",
    "El Roble",
    "La Cumbre",
    "Santa Rosa",
    "El Cafetal",
    "Las Nubes",
    "La Palma",
    "El Recuerdo",
    "Buenavista",
)
VARIETIES = (
    "Bourbon",
    "Caturra",
    "Typica",
    "Catuai",
    "Geisha",
    "Pacamara",
    "Castillo",
    "SL28",
    "SL34",
    "Heirloom",
)
ORIGIN_PORTS = {
    "geo.colombia": "Cartagena",
    "geo.ethiopia": "Djibouti",
    "geo.guatemala": "Puerto Barrios",
    "geo.honduras": "Puerto Cortes",
    "geo.kenya": "Mombasa",
    "geo.peru": "Callao",
}
DESTINATION_PORTS = ("Barcelona", "Valencia")
BLEND_NAMES = (
    "Cumbre House",
    "Trueno",
    "Madrugada",
    "Ember",
    "Solsticio",
    "Nocturno",
    "Marea",
    "Campana",
)
DECAF_NAMES = ("Sierra Decaf", "Valle Decaf")
BLEND_CATEGORIES = ("category.blend", "category.espresso-blend", "category.filter-blend")


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


@dataclass(frozen=True)
class _Spec:
    """What is fixed about a lot before its values are drawn."""

    shipment: Shipment
    cooperative: Cooperative
    window: tuple[date, date]
    farms: tuple[str, ...] | None


@dataclass(frozen=True)
class _World:
    countries: tuple[str, ...]
    cooperatives_by_country: dict[str, tuple[Cooperative, ...]]
    farms_by_cooperative: dict[str, tuple[str, ...]]
    shipments: tuple[Shipment, ...]
    shipments_by_country: dict[str, tuple[Shipment, ...]]
    country_of_shipment: dict[str, str]


def generate_supply(taxonomy: Taxonomy, rng: random.Random) -> Supply:
    countries = _countries(taxonomy)
    cooperatives = _cooperatives(taxonomy, countries, rng)
    certifications = _certifications(cooperatives, rng)
    farms = _farms(cooperatives, rng)
    shipments, country_of_shipment = _shipments(countries, rng)
    world = _World(
        countries=countries,
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
    lots, lot_farms = _lots(taxonomy, world, cooperatives, rng)
    products, product_flavours = _products(taxonomy, rng)
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


def _random_date(rng: random.Random, first: date, last: date) -> date:
    return first + timedelta(days=rng.randint(0, (last - first).days))


def _decimal(hundredths: int) -> Decimal:
    return (Decimal(hundredths) / 100).quantize(Decimal("0.01"))


def _country_of(taxonomy: Taxonomy, region_key: str) -> str:
    parent = taxonomy.get(region_key).parent_key
    if parent is None:
        raise ValueError(f"region {region_key} has no country")
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
            planted.LAPSED_COOPERATIVE, "organic", date(2022, 1, 1), planted.LAPSE_DATE
        )
    ]
    for code in sorted(rng.sample(others, OTHER_ORGANIC_COOPERATIVES)):
        rows.append(
            CooperativeCertification(
                code, "organic", _random_date(rng, date(2019, 1, 1), date(2022, 12, 31)), None
            )
        )
    for code in sorted(rng.sample(codes, FAIR_TRADE_COOPERATIVES)):
        rows.append(
            CooperativeCertification(
                code, "fair_trade", _random_date(rng, date(2018, 1, 1), date(2023, 6, 30)), None
            )
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
            _random_date(rng, *EARLY_DEPARTURE) for _ in range(EARLY_SHIPMENTS_PER_COUNTRY)
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


def _harvest_bounds(shipment: Shipment, window: tuple[date, date]) -> tuple[date, date]:
    nearest, farthest = HARVEST_LEAD_DAYS
    return (
        max(window[0], shipment.departed_on - timedelta(days=farthest)),
        min(window[1], shipment.departed_on - timedelta(days=nearest)),
    )


def _fits(shipment: Shipment, window: tuple[date, date]) -> bool:
    first, last = _harvest_bounds(shipment, window)
    return first <= last


def _cover_then_sample(
    farms: list[str], count: int, rng: random.Random
) -> list[tuple[str, ...]]:
    """`count` farm sets from `farms`: the first ones cover every farm, the rest are random."""
    sets = [tuple(farms[i : i + 3]) for i in range(0, len(farms), 3)]
    if count < len(sets):
        raise ValueError("too few lots to cover every farm of the pool")
    while len(sets) < count:
        size = rng.randint(1, min(3, len(farms)))
        sets.append(tuple(sorted(rng.sample(farms, size))))
    return sets


def _pool_specs(world: _World, rng: random.Random) -> list[_Spec]:
    """The 24 blend pool lots: two pools of 12 whose farm sets overlap in exactly SHARED_FARMS."""
    country = world.countries[POOL_COUNTRY_INDEX]
    first, second = world.cooperatives_by_country[country][:2]
    shipments = world.shipments_by_country[country]
    early = shipments[:EARLY_SHIPMENTS_PER_COUNTRY]
    first_farms = world.farms_by_cooperative[first.code]
    second_farms = world.farms_by_cooperative[second.code]
    interleaved = [farm for pair in zip(first_farms, second_farms, strict=True) for farm in pair]
    shared = interleaved[: planted.SHARED_FARMS]
    start = planted.SHARED_FARMS
    only_alba = interleaved[start : start + POOL_ONLY_FARMS]
    only_brisa = interleaved[start + POOL_ONLY_FARMS : start + 2 * POOL_ONLY_FARMS]
    specs = []
    for pool_farms in (shared + only_alba, shared + only_brisa):
        per_cooperative = []
        for cooperative, own in ((first, first_farms), (second, second_farms)):
            chosen = [farm for farm in pool_farms if farm in own]
            per_cooperative.append(
                (cooperative, _cover_then_sample(chosen, POOL_SIZE // 2, rng))
            )
        for position in range(POOL_SIZE):
            cooperative, farm_sets = per_cooperative[position % 2]
            if position < POOL_LOTS_ON_EARLY_SHIPMENTS:
                shipment = early[position % len(early)]
            else:
                shipment = rng.choice(shipments)
            specs.append(
                _Spec(shipment, cooperative, (HARVEST_START, HARVEST_END), farm_sets[position // 2])
            )
    return specs


def _recalled_specs(world: _World, rng: random.Random) -> dict[int, _Spec]:
    specs = {}
    for code in planted.RECALLED_LOTS:
        deadline = planted.RECALL_DATES[code] - timedelta(days=RECALL_LEAD_DAYS)
        shipment = rng.choice([s for s in world.shipments if s.arrived_on <= deadline])
        country = world.country_of_shipment[shipment.code]
        cooperative = rng.choice(world.cooperatives_by_country[country])
        specs[int(code.removeprefix("L-")) - 1] = _Spec(
            shipment, cooperative, (HARVEST_START, HARVEST_END), None
        )
    return specs


def _lapsed_specs(world: _World, cooperatives: tuple[Cooperative, ...], rng: random.Random) -> list[_Spec]:
    """Lots of the lapsed cooperative harvested in 2025 before and after its certificate ends."""
    lapsed = next(c for c in cooperatives if c.code == planted.LAPSED_COOPERATIVE)
    country = next(
        country
        for country, members in world.cooperatives_by_country.items()
        if lapsed in members
    )
    before = (date(2025, 1, 1), planted.LAPSE_DATE)
    after = (planted.LAPSE_DATE + timedelta(days=1), HARVEST_END)
    specs = []
    for window in [before] * LAPSED_LOTS_PER_SIDE + [after] * LAPSED_LOTS_PER_SIDE:
        shipment = rng.choice([s for s in world.shipments_by_country[country] if _fits(s, window)])
        specs.append(_Spec(shipment, lapsed, window, None))
    return specs


def _lot_specs(
    world: _World, cooperatives: tuple[Cooperative, ...], rng: random.Random
) -> list[_Spec]:
    placed: dict[int, _Spec] = dict(enumerate(_pool_specs(world, rng)))
    placed.update(_recalled_specs(world, rng))
    free = [i for i in range(LOT_COUNT) if i not in placed]
    lapsed = _lapsed_specs(world, cooperatives, rng)
    for index, spec in zip(sorted(rng.sample(free, len(lapsed))), lapsed, strict=True):
        placed[index] = spec
    per_shipment = {s.code: 0 for s in world.shipments}
    for spec in placed.values():
        per_shipment[spec.shipment.code] += 1
    slots = [
        s
        for s in world.shipments
        for _ in range(max(0, MIN_LOTS_PER_SHIPMENT - per_shipment[s.code]))
    ]
    ordinary = [i for i in range(LOT_COUNT) if i not in placed]
    slots += [rng.choice(world.shipments) for _ in range(len(ordinary) - len(slots))]
    rng.shuffle(slots)
    for index, shipment in zip(ordinary, slots, strict=True):
        country = world.country_of_shipment[shipment.code]
        cooperative = rng.choice(world.cooperatives_by_country[country])
        placed[index] = _Spec(shipment, cooperative, (HARVEST_START, HARVEST_END), None)
    return [placed[i] for i in range(LOT_COUNT)]


def _lots(
    taxonomy: Taxonomy,
    world: _World,
    cooperatives: tuple[Cooperative, ...],
    rng: random.Random,
) -> tuple[tuple[Lot, ...], tuple[LotFarm, ...]]:
    processes = [c.key for c in taxonomy.in_scheme("process")]
    lots = []
    links = []
    for index, spec in enumerate(_lot_specs(world, cooperatives, rng)):
        code = f"L-{index + 1:04d}"
        first, last = _harvest_bounds(spec.shipment, spec.window)
        farms = spec.farms
        if farms is None:
            own = world.farms_by_cooperative[spec.cooperative.code]
            farms = tuple(sorted(rng.sample(own, rng.randint(1, 3))))
        lots.append(
            Lot(
                code=code,
                cooperative_code=spec.cooperative.code,
                shipment_code=spec.shipment.code,
                process_key=rng.choice(processes),
                variety=rng.choice(VARIETIES),
                harvested_on=_random_date(rng, first, last),
                weight_kg=_decimal(rng.randint(60000, 300000)),
                price_per_kg=_decimal(rng.randint(400, 1400)),
            )
        )
        links += [LotFarm(code, farm) for farm in farms]
    return tuple(lots), tuple(links)


def _products(
    taxonomy: Taxonomy, rng: random.Random
) -> tuple[tuple[Product, ...], tuple[ProductFlavour, ...]]:
    regions = list(taxonomy.leaves("geo"))
    rng.shuffle(regions)
    named: list[tuple[str, str]] = []
    for index in range(SINGLE_ORIGIN_PRODUCTS):
        region = regions[index % len(regions)].label_en
        if index >= len(regions):
            named.append((f"{region} Reserve", "category.single-origin"))
        elif index % 4 == 3:
            named.append((f"{region} Microlot", "category.microlot"))
        else:
            named.append((f"{region} Classic", "category.single-origin"))
    named.append(("Alba", "category.espresso-blend"))
    named.append(("Brisa", "category.filter-blend"))
    for name in BLEND_NAMES[: BLEND_PRODUCTS - len(planted.BLENDS)]:
        named.append((name, rng.choice(BLEND_CATEGORIES)))
    named += [(name, "category.decaf") for name in DECAF_NAMES[:DECAF_PRODUCTS]]
    rng.shuffle(named)
    flavours = [c.key for c in taxonomy.leaves("flavour")]
    products = []
    links = []
    for index, (name, category) in enumerate(named):
        code = f"P-{index + 1:02d}"
        bag_weight = rng.choice((250, 1000))
        price = rng.randint(600, 1400) if bag_weight == 250 else rng.randint(2000, 5000)
        products.append(Product(code, name, category, bag_weight, _decimal(price)))
        for flavour in sorted(rng.sample(flavours, rng.randint(1, 3))):
            links.append(ProductFlavour(code, flavour))
    return tuple(products), tuple(links)
