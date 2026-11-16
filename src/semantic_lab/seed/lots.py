"""Lot placement: which shipment and cooperative each lot belongs to, and its farms and values.

The facts in `planted` hold by construction, so they hold for every seed: the pool lots, the
recalled lots and the lapsed cooperative's lots are placed first, and the ordinary lots fill
the rest.
"""

import random
from dataclasses import dataclass
from datetime import date, timedelta

from semantic_lab.domain.errors import GenerationError
from semantic_lab.domain.records import Cooperative, Lot, LotFarm, Shipment
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import planted
from semantic_lab.seed.draw import decimal_from_hundredths, random_date
from semantic_lab.seed.names import VARIETIES

HARVEST_START = date(2023, 10, 1)
HARVEST_END = date(2025, 9, 30)
LAPSE_YEAR_START = date(2025, 1, 1)

LOT_COUNT = 600
MAX_FARMS_PER_LOT = 3
MIN_LOTS_PER_SHIPMENT = 6
# The shipments of a country that sail first. The supply module gives them departures early
# enough to arrive before roasting starts, and the pool lots rely on that.
EARLY_SHIPMENTS_PER_COUNTRY = 2
# A lot is harvested this many days before its shipment sails, at the earliest and the latest.
HARVEST_LEAD_DAYS = (5, 45)

# How often each processing method is drawn, as integer weights keyed by concept key. Washed is
# the most common method and the honey family together holds about a quarter of the lots.
PROCESS_WEIGHTS = {
    "process.washed": 50,
    "process.natural": 18,
    "process.anaerobic-natural": 5,
    "process.honey": 9,
    "process.yellow-honey": 7,
    "process.red-honey": 6,
    "process.black-honey": 5,
}

POOL_COUNTRY = "geo.ethiopia"
POOL_SIZE = 12
POOL_ONLY_FARMS = 3
POOL_LOTS_ON_EARLY_SHIPMENTS = 6
LAPSED_LOTS_PER_SIDE = 6
RECALL_LEAD_DAYS = 60


@dataclass(frozen=True)
class Spec:
    """What is fixed about a lot before its values are drawn."""

    shipment: Shipment
    cooperative: Cooperative
    window: tuple[date, date]
    farms: tuple[str, ...] | None


@dataclass(frozen=True)
class World:
    """The cooperatives, farms and shipments the lots are placed among."""

    cooperatives_by_country: dict[str, tuple[Cooperative, ...]]
    farms_by_cooperative: dict[str, tuple[str, ...]]
    shipments: tuple[Shipment, ...]
    shipments_by_country: dict[str, tuple[Shipment, ...]]
    country_of_shipment: dict[str, str]


def generate_lots(
    taxonomy: Taxonomy,
    world: World,
    cooperatives: tuple[Cooperative, ...],
    rng: random.Random,
) -> tuple[tuple[Lot, ...], tuple[LotFarm, ...]]:
    processes = sorted(c.key for c in taxonomy.in_scheme("process"))
    process_weights = [PROCESS_WEIGHTS[key] for key in processes]
    lots = []
    links = []
    for index, spec in enumerate(_lot_specs(world, cooperatives, rng)):
        code = f"L-{index + 1:04d}"
        first, last = _harvest_bounds(spec.shipment, spec.window)
        farms = spec.farms
        if farms is None:
            own = world.farms_by_cooperative[spec.cooperative.code]
            farms = tuple(sorted(rng.sample(own, rng.randint(1, MAX_FARMS_PER_LOT))))
        lots.append(
            Lot(
                code=code,
                cooperative_code=spec.cooperative.code,
                shipment_code=spec.shipment.code,
                process_key=rng.choices(processes, weights=process_weights)[0],
                variety=rng.choice(VARIETIES),
                harvested_on=random_date(rng, first, last),
                weight_kg=decimal_from_hundredths(rng.randint(60000, 300000)),
                price_per_kg=decimal_from_hundredths(rng.randint(400, 1400)),
            )
        )
        links += [LotFarm(code, farm) for farm in farms]
    return tuple(lots), tuple(links)


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
    size = MAX_FARMS_PER_LOT
    sets = [tuple(farms[i : i + size]) for i in range(0, len(farms), size)]
    if count < len(sets):
        raise GenerationError("too few lots to cover every farm of the pool")
    while len(sets) < count:
        sets.append(tuple(sorted(rng.sample(farms, rng.randint(1, min(size, len(farms)))))))
    return sets


def _pool_specs(world: World, rng: random.Random) -> list[Spec]:
    """The 24 blend pool lots: two pools of 12 whose farm sets overlap in exactly SHARED_FARMS."""
    country = POOL_COUNTRY
    first, second = world.cooperatives_by_country[country][:2]
    shipments = world.shipments_by_country[country]
    # The country's shipments are in departure order, so the first ones are the early ones.
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
                Spec(shipment, cooperative, (HARVEST_START, HARVEST_END), farm_sets[position // 2])
            )
    return specs


def _recalled_specs(world: World, rng: random.Random) -> dict[int, Spec]:
    specs = {}
    for code in planted.RECALLED_LOTS:
        deadline = planted.RECALL_DATES[code] - timedelta(days=RECALL_LEAD_DAYS)
        shipment = rng.choice([s for s in world.shipments if s.arrived_on <= deadline])
        country = world.country_of_shipment[shipment.code]
        cooperative = rng.choice(world.cooperatives_by_country[country])
        specs[int(code.removeprefix("L-")) - 1] = Spec(
            shipment, cooperative, (HARVEST_START, HARVEST_END), None
        )
    return specs


def _lapsed_specs(
    world: World, cooperatives: tuple[Cooperative, ...], rng: random.Random
) -> list[Spec]:
    """Lots of the lapsed cooperative harvested in 2025 before and after its certificate ends."""
    lapsed = next(c for c in cooperatives if c.code == planted.LAPSED_COOPERATIVE)
    country = next(
        country
        for country, members in world.cooperatives_by_country.items()
        if lapsed in members
    )
    before = (LAPSE_YEAR_START, planted.LAPSE_DATE)
    after = (planted.LAPSE_DATE + timedelta(days=1), HARVEST_END)
    specs = []
    for window in [before] * LAPSED_LOTS_PER_SIDE + [after] * LAPSED_LOTS_PER_SIDE:
        shipment = rng.choice([s for s in world.shipments_by_country[country] if _fits(s, window)])
        specs.append(Spec(shipment, lapsed, window, None))
    return specs


def _lot_specs(
    world: World, cooperatives: tuple[Cooperative, ...], rng: random.Random
) -> list[Spec]:
    placed: dict[int, Spec] = dict(enumerate(_pool_specs(world, rng)))
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
        placed[index] = Spec(shipment, cooperative, (HARVEST_START, HARVEST_END), None)
    return [placed[i] for i in range(LOT_COUNT)]
