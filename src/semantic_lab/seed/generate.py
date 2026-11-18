"""The whole dataset from one seed, and the digest that pins it."""

import hashlib
import random
from dataclasses import fields

from semantic_lab.domain.records import Dataset
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import requirements
from semantic_lab.seed.sales import generate_sales
from semantic_lab.seed.supply import generate_supply

DEFAULT_SEED = 20240101


def generate(taxonomy: Taxonomy, seed: int) -> Dataset:
    requirements.check(taxonomy)
    rng = random.Random(seed)
    supply = generate_supply(taxonomy, rng)
    sales = generate_sales(supply, rng)
    return Dataset(
        cooperatives=supply.cooperatives,
        certifications=supply.certifications,
        farms=supply.farms,
        shipments=supply.shipments,
        lots=supply.lots,
        lot_farms=supply.lot_farms,
        products=supply.products,
        product_flavours=supply.product_flavours,
        roast_batches=sales.roast_batches,
        roast_batch_lots=sales.roast_batch_lots,
        customers=sales.customers,
        orders=sales.orders,
        order_lines=sales.order_lines,
        quality_incidents=sales.quality_incidents,
    )


def digest(dataset: Dataset) -> str:
    """The sha256 of every row's repr, table by table in the dataset's order."""
    hasher = hashlib.sha256()
    for table in fields(dataset):
        for row in getattr(dataset, table.name):
            hasher.update(repr(row).encode())
            hasher.update(b"\n")
    return hasher.hexdigest()
