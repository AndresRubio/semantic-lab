"""The sales side of the seed: roast batches, customers, orders, order lines and incidents.

Everything here is a pure function of the supply and the random generator passed in. Batches
are planned in `batches`, orders in `orders`, and `recalls` ties the recalled lots to
customers. A batch's output is set last, from what its order lines took.
"""

import random
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from semantic_lab.domain.records import (
    Customer,
    OrderLine,
    QualityIncident,
    RoastBatch,
    RoastBatchLot,
    SalesOrder,
)
from semantic_lab.seed import planted
from semantic_lab.seed.batches import finish_batches, generate_batches
from semantic_lab.seed.orders import draft_orders, finish_orders, generate_customers
from semantic_lab.seed.recalls import reach_recalled
from semantic_lab.seed.supply import Supply

RECALL_DESCRIPTIONS = (
    "Cupping found a fermentation defect after the lot had been roasted and shipped.",
    "A supplier alert reported mould on part of the lot after it had been roasted and shipped.",
)


@dataclass(frozen=True)
class Sales:
    roast_batches: tuple[RoastBatch, ...]
    roast_batch_lots: tuple[RoastBatchLot, ...]
    customers: tuple[Customer, ...]
    orders: tuple[SalesOrder, ...]
    order_lines: tuple[OrderLine, ...]
    quality_incidents: tuple[QualityIncident, ...]


def generate_sales(supply: Supply, rng: random.Random) -> Sales:
    batches = generate_batches(supply, rng)
    customers = generate_customers(rng)
    drafted = draft_orders(supply.products, customers, batches, rng)
    reach_recalled(drafted, batches, rng)
    orders, lines = finish_orders(drafted, supply.products)
    roast_batches = finish_batches(batches, _sold_kg(lines), rng)
    return Sales(
        roast_batches=roast_batches,
        roast_batch_lots=batches.roast_batch_lots,
        customers=customers,
        orders=orders,
        order_lines=lines,
        quality_incidents=_incidents(),
    )


def _sold_kg(lines: tuple[OrderLine, ...]) -> dict[str, Decimal]:
    sold: dict[str, Decimal] = defaultdict(Decimal)
    for line in lines:
        sold[line.roast_batch_code] += line.kg
    return dict(sold)


def _incidents() -> tuple[QualityIncident, ...]:
    return tuple(
        QualityIncident(
            code=f"Q-{index + 1:02d}",
            lot_code=lot,
            kind="recall",
            reported_on=planted.RECALL_DATES[lot],
            description=RECALL_DESCRIPTIONS[index],
        )
        for index, lot in enumerate(planted.RECALLED_LOTS)
    )
