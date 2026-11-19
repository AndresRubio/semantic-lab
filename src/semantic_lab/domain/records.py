from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal
from typing import Any, get_args, get_type_hints


@dataclass(frozen=True)
class Cooperative:
    code: str
    name: str
    region_key: str


@dataclass(frozen=True)
class CooperativeCertification:
    cooperative_code: str
    certification: str
    valid_from: date
    valid_until: date | None


@dataclass(frozen=True)
class Farm:
    code: str
    name: str
    cooperative_code: str
    altitude_m: int


@dataclass(frozen=True)
class Shipment:
    code: str
    origin_port: str
    destination_port: str
    departed_on: date
    arrived_on: date


@dataclass(frozen=True)
class Lot:
    code: str
    cooperative_code: str
    shipment_code: str
    process_key: str
    variety: str
    harvested_on: date
    weight_kg: Decimal
    price_per_kg: Decimal


@dataclass(frozen=True)
class LotFarm:
    lot_code: str
    farm_code: str


@dataclass(frozen=True)
class Product:
    code: str
    name: str
    category_key: str
    origin_region_key: str | None
    bag_weight_g: int
    list_price: Decimal


@dataclass(frozen=True)
class ProductFlavour:
    product_code: str
    flavour_key: str


@dataclass(frozen=True)
class RoastBatch:
    code: str
    product_code: str
    roasted_on: date
    output_kg: Decimal
    cost_per_kg: Decimal


@dataclass(frozen=True)
class RoastBatchLot:
    roast_batch_code: str
    lot_code: str
    share: Decimal


@dataclass(frozen=True)
class Customer:
    code: str
    name: str
    segment: str
    city: str
    country: str


@dataclass(frozen=True)
class SalesOrder:
    code: str
    customer_code: str
    ordered_on: date


@dataclass(frozen=True)
class OrderLine:
    order_code: str
    line_no: int
    product_code: str
    roast_batch_code: str
    bags: int
    unit_price: Decimal
    amount: Decimal
    kg: Decimal


@dataclass(frozen=True)
class QualityIncident:
    code: str
    lot_code: str
    kind: str
    reported_on: date
    description: str


@dataclass(frozen=True)
class Dataset:
    """Every data table of the seed, in the order of the data model."""

    cooperatives: tuple[Cooperative, ...]
    certifications: tuple[CooperativeCertification, ...]
    farms: tuple[Farm, ...]
    shipments: tuple[Shipment, ...]
    lots: tuple[Lot, ...]
    lot_farms: tuple[LotFarm, ...]
    products: tuple[Product, ...]
    product_flavours: tuple[ProductFlavour, ...]
    roast_batches: tuple[RoastBatch, ...]
    roast_batch_lots: tuple[RoastBatchLot, ...]
    customers: tuple[Customer, ...]
    orders: tuple[SalesOrder, ...]
    order_lines: tuple[OrderLine, ...]
    quality_incidents: tuple[QualityIncident, ...]


# Each data table with the Dataset attribute that holds its rows, in creation order.
DATA_TABLES: tuple[tuple[str, str], ...] = (
    ("cooperative", "cooperatives"),
    ("cooperative_certification", "certifications"),
    ("farm", "farms"),
    ("shipment", "shipments"),
    ("lot", "lots"),
    ("lot_farm", "lot_farms"),
    ("product", "products"),
    ("product_flavour", "product_flavours"),
    ("roast_batch", "roast_batches"),
    ("roast_batch_lot", "roast_batch_lots"),
    ("customer", "customers"),
    ("sales_order", "orders"),
    ("order_line", "order_lines"),
    ("quality_incident", "quality_incidents"),
)


def _attribute(table: str) -> str:
    for name, attribute in DATA_TABLES:
        if name == table:
            return attribute
    raise KeyError(table)


def record_type(table: str) -> type[Any]:
    """The record class of a data table. A name that is no data table is a KeyError."""
    return get_args(get_type_hints(Dataset)[_attribute(table)])[0]


def columns(table: str) -> tuple[str, ...]:
    """The columns of a data table: its record class's fields, in order. A KeyError if no table."""
    return tuple(field.name for field in fields(record_type(table)))


def column_types(table: str) -> dict[str, type[Any]]:
    """The Python type of each column of a data table, a nullable one without its None.

    It reads a field as a plain type or as `X | None`, which is all the record classes use.
    """
    found: dict[str, type[Any]] = {}
    for name, hint in get_type_hints(record_type(table)).items():
        held = [part for part in get_args(hint) if part is not type(None)]
        found[name] = held[0] if held else hint
    return found


def rows(dataset: Dataset, table: str) -> tuple[Any, ...]:
    """The rows of a data table, in the dataset's order."""
    return getattr(dataset, _attribute(table))
