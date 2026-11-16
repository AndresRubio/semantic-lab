"""The product range: single-origin and microlot coffees, blends and decafs."""

import random

from semantic_lab.domain.records import Product, ProductFlavour
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import planted
from semantic_lab.seed.draw import decimal_from_hundredths

SINGLE_ORIGIN_PRODUCTS = 28
BLEND_PRODUCTS = 10
DECAF_PRODUCTS = 2
MAX_FLAVOUR_NOTES = 3

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


def generate_products(
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
        products.append(Product(code, name, category, bag_weight, decimal_from_hundredths(price)))
        for flavour in sorted(rng.sample(flavours, rng.randint(1, MAX_FLAVOUR_NOTES))):
            links.append(ProductFlavour(code, flavour))
    return tuple(products), tuple(links)
