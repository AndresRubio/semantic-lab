"""What the tests of the seed generator share: seeds, the generated world and small lookups."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from semantic_lab.domain.records import OrderLine, Product
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed.generate import DEFAULT_SEED
from semantic_lab.seed.sales import Sales
from semantic_lab.seed.supply import Supply

# Planted facts hold for any seed, so every test of the generator runs against each of these.
SEEDS = (DEFAULT_SEED, 1, 7, 99)
EARLY_END = date(2023, 12, 31)
ONE_LOT_CATEGORIES = ("category.single-origin", "category.microlot", "category.decaf")
BLEND_CATEGORIES = ("category.blend", "category.espresso-blend", "category.filter-blend")
CENTS = Decimal("0.01")


@dataclass(frozen=True)
class World:
    supply: Supply
    sales: Sales


def country_of_region(taxonomy: Taxonomy, region_key: str) -> str:
    parent = taxonomy.get(region_key).parent_key
    assert parent is not None
    return parent


def lot_countries(supply: Supply, taxonomy: Taxonomy) -> dict[str, str]:
    region_of = {c.code: c.region_key for c in supply.cooperatives}
    return {
        lot.code: country_of_region(taxonomy, region_of[lot.cooperative_code])
        for lot in supply.lots
    }


def lot_regions(supply: Supply) -> dict[str, str]:
    region_of = {c.code: c.region_key for c in supply.cooperatives}
    return {lot.code: region_of[lot.cooperative_code] for lot in supply.lots}


def lot_arrivals(supply: Supply) -> dict[str, date]:
    arrival = {s.code: s.arrived_on for s in supply.shipments}
    return {lot.code: arrival[lot.shipment_code] for lot in supply.lots}


def product_named(supply: Supply, name: str) -> Product:
    return next(p for p in supply.products if p.name == name)


def lots_of_batches(sales: Sales) -> dict[str, list[tuple[str, Decimal]]]:
    found: dict[str, list[tuple[str, Decimal]]] = defaultdict(list)
    for link in sales.roast_batch_lots:
        found[link.roast_batch_code].append((link.lot_code, link.share))
    return found


def sold_kg(sales: Sales) -> dict[str, Decimal]:
    """The kilograms on the order lines of each batch that has any."""
    found: dict[str, Decimal] = defaultdict(Decimal)
    for line in sales.order_lines:
        found[line.roast_batch_code] += line.kg
    return dict(found)


def lines_by_order(sales: Sales) -> dict[str, list[OrderLine]]:
    found: dict[str, list[OrderLine]] = defaultdict(list)
    for line in sales.order_lines:
        found[line.order_code].append(line)
    return found
