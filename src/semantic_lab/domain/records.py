from dataclasses import dataclass
from datetime import date
from decimal import Decimal


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
