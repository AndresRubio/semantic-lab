"""Customers, orders and order lines.

Lines are first drafted against the ordinary batches only. `recalls` then redirects a few
of them to the batches that consume a recalled lot, and `finish_orders` turns the drafts into
rows.
"""

import random
from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from itertools import accumulate

from semantic_lab.domain.records import Customer, OrderLine, Product, SalesOrder
from semantic_lab.seed.batches import Batches, PlannedBatch, recalled_batches
from semantic_lab.seed.names import CUSTOMER_CITIES, CUSTOMER_PREFIXES, CUSTOMER_WORDS

SEGMENT_COUNTS = (("cafe", 130), ("shop", 100), ("restaurant", 70))
ORDER_COUNT = 20000
LINE_COUNT = 60000
FIRST_ORDER_DAY = date(2024, 1, 2)
LAST_ORDER_DAY = date(2025, 12, 31)
# Monday to Sunday: weekends are quiet.
WEEKDAY_WEIGHTS = (10, 10, 10, 10, 10, 4, 1)
# Weights of an order having 1 to 6 lines. The draw is then corrected to LINE_COUNT in total.
LINES_PER_ORDER_WEIGHTS = (15, 25, 25, 18, 10, 7)
MAX_BAGS = 40
CUSTOMER_ACTIVITY = (1, 6)
PRODUCT_POPULARITY = (1, 5)
# A line is filled from one of the most recent batches of its product.
RECENT_BATCHES = 3


@dataclass(slots=True)
class Draft:
    """A line before it is final: its batch can still change."""

    order_code: str
    customer_code: str
    ordered_on: date
    line_no: int
    product_code: str
    batch_code: str
    bags: int
    pinned: bool = False


@dataclass(frozen=True)
class Drafted:
    orders: tuple[SalesOrder, ...]
    lines: list[Draft]


class _Shelf:
    """The ordinary batches of each product by roasting day: what a line can be filled from."""

    def __init__(self, batches: tuple[PlannedBatch, ...], excluded: set[str]) -> None:
        self._days: dict[str, list[date]] = {}
        self._codes: dict[str, list[str]] = {}
        for batch in batches:
            if batch.code not in excluded:
                self._days.setdefault(batch.product_code, []).append(batch.roasted_on)
                self._codes.setdefault(batch.product_code, []).append(batch.code)

    def first_day(self, product_code: str) -> date:
        return self._days[product_code][0]

    def pick(self, product_code: str, day: date, rng: random.Random) -> str:
        end = bisect_right(self._days[product_code], day)
        return self._codes[product_code][end - 1 - rng.randrange(min(RECENT_BATCHES, end))]


def generate_customers(rng: random.Random) -> tuple[Customer, ...]:
    named = []
    for segment, count in SEGMENT_COUNTS:
        names = [
            f"{prefix} {word}" for prefix in CUSTOMER_PREFIXES[segment] for word in CUSTOMER_WORDS
        ]
        named += [(segment, name) for name in rng.sample(names, count)]
    rng.shuffle(named)
    customers = []
    for index, (segment, name) in enumerate(named):
        city, country = rng.choice(CUSTOMER_CITIES)
        customers.append(Customer(f"K-{index + 1:03d}", name, segment, city, country))
    return tuple(customers)


def draft_orders(
    products: tuple[Product, ...],
    customers: tuple[Customer, ...],
    batches: Batches,
    rng: random.Random,
) -> Drafted:
    shelf = _Shelf(batches.planned, _recalled_codes(batches))
    span = (LAST_ORDER_DAY - FIRST_ORDER_DAY).days + 1
    days = [FIRST_ORDER_DAY + timedelta(days=i) for i in range(span)]
    dates = sorted(
        rng.choices(days, weights=[WEEKDAY_WEIGHTS[d.weekday()] for d in days], k=ORDER_COUNT)
    )
    activity = [rng.randint(*CUSTOMER_ACTIVITY) for _ in customers]
    buyers = rng.choices(customers, weights=activity, k=ORDER_COUNT)
    counts = _lines_per_order(rng)
    popularity = list(accumulate(rng.randint(*PRODUCT_POPULARITY) for _ in products))
    bag_weights = list(accumulate(range(MAX_BAGS, 0, -1)))
    orders = []
    lines = []
    for index, (day, buyer, count) in enumerate(zip(dates, buyers, counts, strict=True)):
        order_code = f"O-{index + 1:05d}"
        orders.append(SalesOrder(order_code, buyer.code, day))
        taken: set[str] = set()
        while len(taken) < count:
            product = rng.choices(products, cum_weights=popularity)[0]
            # Ten products have a batch on the first day, so a day never runs out of products.
            if product.code in taken or shelf.first_day(product.code) > day:
                continue
            taken.add(product.code)
            lines.append(
                Draft(
                    order_code=order_code,
                    customer_code=buyer.code,
                    ordered_on=day,
                    line_no=len(taken),
                    product_code=product.code,
                    batch_code=shelf.pick(product.code, day, rng),
                    bags=rng.choices(range(1, MAX_BAGS + 1), cum_weights=bag_weights)[0],
                )
            )
    return Drafted(tuple(orders), lines)


def finish_orders(
    drafted: Drafted, products: tuple[Product, ...]
) -> tuple[tuple[SalesOrder, ...], tuple[OrderLine, ...]]:
    by_code = {p.code: p for p in products}
    lines = []
    for draft in drafted.lines:
        product = by_code[draft.product_code]
        lines.append(
            OrderLine(
                order_code=draft.order_code,
                line_no=draft.line_no,
                product_code=draft.product_code,
                roast_batch_code=draft.batch_code,
                bags=draft.bags,
                unit_price=product.list_price,
                amount=draft.bags * product.list_price,
                kg=(Decimal(draft.bags * product.bag_weight_g) / 1000).quantize(Decimal("0.001")),
            )
        )
    return drafted.orders, tuple(lines)


def _recalled_codes(batches: Batches) -> set[str]:
    return {code for codes in recalled_batches(batches).values() for code in codes}


def _lines_per_order(rng: random.Random) -> list[int]:
    counts = rng.choices(range(1, 7), weights=LINES_PER_ORDER_WEIGHTS, k=ORDER_COUNT)
    while (excess := sum(counts) - LINE_COUNT) != 0:
        index = rng.randrange(ORDER_COUNT)
        if excess > 0 and counts[index] > 1:
            counts[index] -= 1
        elif excess < 0 and counts[index] < 6:
            counts[index] += 1
    return counts
