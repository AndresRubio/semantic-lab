"""Roast batches: which product is roasted on which day, and from which lots.

A batch may only use lots whose shipment arrived before the roasting day. The recalled lots
are used by the batches planned for them and by no other, so how many batches a recall
touches is decided here and not left to chance.
"""

import random
from bisect import bisect_left
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from semantic_lab.domain.records import Product, RoastBatch, RoastBatchLot
from semantic_lab.seed import planted
from semantic_lab.seed.draw import decimal_from_hundredths, random_date
from semantic_lab.seed.names import ORIGIN_PORTS
from semantic_lab.seed.products import BLEND_CATEGORIES
from semantic_lab.seed.supply import Supply

BATCH_COUNT = 3000
FIRST_ROAST_DAY = date(2024, 1, 2)
LAST_ROAST_DAY = date(2025, 12, 28)
# The first batch of each product falls in the first FIRST_BATCH_DAYS days, so orders can start
# on day one with ten products on offer.
FIRST_BATCH_DAYS = 4
OUTPUT_HUNDREDTHS = (6000, 40000)
ROAST_YIELD = Decimal("0.85")
ONE_LOT_CATEGORIES = ("category.single-origin", "category.microlot", "category.decaf")
BLEND_LOTS = (2, 4)
MAX_BLEND_WEIGHT = 10
RECALLED_BATCHES = (3, 6)
# A recalled lot's batches are roasted at least this long before the recall, so the lines that
# carry them have time to be ordered.
RECALL_LEAD_DAYS = 30

PORT_COUNTRY = {port: country for country, port in ORIGIN_PORTS.items()}


@dataclass(frozen=True)
class Batches:
    roast_batches: tuple[RoastBatch, ...]
    roast_batch_lots: tuple[RoastBatchLot, ...]


@dataclass(frozen=True)
class _Plan:
    product: Product
    roasted_on: date
    forced_lot: str | None


class _Arrivals:
    """Lot codes in order of arrival, so the lots usable on a day are a prefix."""

    def __init__(self, arrivals: dict[str, date], codes: list[str]) -> None:
        ordered = sorted((arrivals[code], code) for code in codes)
        self._days = [day for day, _ in ordered]
        self._codes = [code for _, code in ordered]

    def before(self, day: date) -> list[str]:
        return self._codes[: bisect_left(self._days, day)]


class _PoolDraw:
    """Draws lots of one blend's pool so that every pool farm is covered soon and use evens out."""

    def __init__(self, farms_of_lot: dict[str, frozenset[str]]) -> None:
        self._farms_of_lot = farms_of_lot
        self._uses: Counter[str] = Counter()
        self._covered: set[str] = set()

    def pick(self, available: list[str], count: int, rng: random.Random) -> list[str]:
        chosen: list[str] = []
        for _ in range(count):
            lot = min(
                (code for code in available if code not in chosen),
                key=lambda code: (
                    -len(self._farms_of_lot[code] - self._covered),
                    self._uses[code],
                    rng.getrandbits(32),
                ),
            )
            chosen.append(lot)
            self._uses[lot] += 1
            self._covered |= self._farms_of_lot[lot]
        return chosen


def generate_batches(supply: Supply, rng: random.Random) -> Batches:
    arrival_of_shipment = {s.code: s.arrived_on for s in supply.shipments}
    arrival = {lot.code: arrival_of_shipment[lot.shipment_code] for lot in supply.lots}
    country = {s.code: PORT_COUNTRY[s.origin_port] for s in supply.shipments}
    lot_country = {lot.code: country[lot.shipment_code] for lot in supply.lots}
    usable = [lot.code for lot in supply.lots if lot.code not in planted.RECALLED_LOTS]
    anywhere = _Arrivals(arrival, usable)
    by_country = {
        name: _Arrivals(arrival, [code for code in usable if lot_country[code] == name])
        for name in sorted(set(country.values()))
    }
    origin_of = _origins(supply.products, sorted(by_country), rng)
    farms_of_lot: dict[str, set[str]] = {lot.code: set() for lot in supply.lots}
    for link in supply.lot_farms:
        farms_of_lot[link.lot_code].add(link.farm_code)
    pools = {
        name: (
            _Arrivals(arrival, list(codes)),
            _PoolDraw({code: frozenset(farms_of_lot[code]) for code in codes}),
        )
        for name, codes in zip(
            planted.BLENDS, (planted.ALBA_POOL, planted.BRISA_POOL), strict=True
        )
    }
    price = {lot.code: lot.price_per_kg for lot in supply.lots}
    batches = []
    links = []
    for index, plan in enumerate(_plans(supply, arrival, rng)):
        product = plan.product
        if product.category_key in ONE_LOT_CATEGORIES:
            usable_lots = by_country[origin_of[product.code]].before(plan.roasted_on)
            lots = [rng.choice(usable_lots)]
        else:
            lots = _blend_lots(plan, anywhere, pools, rng)
        shares = _shares(len(lots), rng)
        code = f"B-{index + 1:04d}"
        for lot, share in sorted(zip(lots, shares, strict=True)):
            links.append(RoastBatchLot(code, lot, share))
        batches.append(
            RoastBatch(
                code=code,
                product_code=product.code,
                roasted_on=plan.roasted_on,
                output_kg=decimal_from_hundredths(rng.randint(*OUTPUT_HUNDREDTHS)),
                cost_per_kg=_cost_per_kg(price, lots, shares),
            )
        )
    return Batches(tuple(batches), tuple(links))


def recalled_batches(batches: Batches) -> dict[str, tuple[str, ...]]:
    """For each recalled lot, the codes of the batches that consume it."""
    found: dict[str, list[str]] = {lot: [] for lot in planted.RECALLED_LOTS}
    for link in batches.roast_batch_lots:
        if link.lot_code in found:
            found[link.lot_code].append(link.roast_batch_code)
    return {lot: tuple(codes) for lot, codes in found.items()}


def _origins(
    products: tuple[Product, ...], countries: list[str], rng: random.Random
) -> dict[str, str]:
    """The one country each single-lot product is made from."""
    codes = [p.code for p in products if p.category_key in ONE_LOT_CATEGORIES]
    rng.shuffle(codes)
    return {code: countries[position % len(countries)] for position, code in enumerate(codes)}


def _plans(supply: Supply, arrival: dict[str, date], rng: random.Random) -> list[_Plan]:
    """Every batch's product and day, in day order. Lots are drawn afterwards, in that order."""
    plans = [
        _Plan(product, FIRST_ROAST_DAY + timedelta(days=index % FIRST_BATCH_DAYS), None)
        for index, product in enumerate(supply.products)
    ]
    ordinary_blends = [
        p
        for p in supply.products
        if p.category_key in BLEND_CATEGORIES and p.name not in planted.BLENDS
    ]
    for lot in planted.RECALLED_LOTS:
        first = max(arrival[lot] + timedelta(days=1), FIRST_ROAST_DAY)
        last = planted.RECALL_DATES[lot] - timedelta(days=RECALL_LEAD_DAYS)
        for _ in range(rng.randint(*RECALLED_BATCHES)):
            plans.append(_Plan(rng.choice(ordinary_blends), random_date(rng, first, last), lot))
    while len(plans) < BATCH_COUNT:
        product = rng.choice(supply.products)
        plans.append(_Plan(product, random_date(rng, FIRST_ROAST_DAY, LAST_ROAST_DAY), None))
    return sorted(plans, key=lambda plan: plan.roasted_on)


def _blend_lots(
    plan: _Plan,
    anywhere: _Arrivals,
    pools: dict[str, tuple[_Arrivals, _PoolDraw]],
    rng: random.Random,
) -> list[str]:
    count = rng.randint(*BLEND_LOTS)
    if plan.product.name in pools:
        arrivals, draw = pools[plan.product.name]
        return draw.pick(arrivals.before(plan.roasted_on), count, rng)
    available = anywhere.before(plan.roasted_on)
    if plan.forced_lot is None:
        return rng.sample(available, count)
    return [plan.forced_lot, *rng.sample(available, count - 1)]


def _shares(count: int, rng: random.Random) -> list[Decimal]:
    """`count` shares in hundredths that sum to exactly 1, each at least 0.02."""
    if count == 1:
        return [Decimal("1.00")]
    weights = [rng.randint(1, MAX_BLEND_WEIGHT) for _ in range(count)]
    hundredths = [100 * weight // sum(weights) for weight in weights]
    hundredths[0] += 100 - sum(hundredths)
    return [decimal_from_hundredths(h) for h in hundredths]


def _cost_per_kg(price: dict[str, Decimal], lots: list[str], shares: list[Decimal]) -> Decimal:
    green = sum(share * price[code] for code, share in zip(lots, shares, strict=True))
    return (green / ROAST_YIELD).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
