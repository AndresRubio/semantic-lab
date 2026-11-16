"""The product range: single-origin and microlot coffees, blends and decafs."""

import random
from collections import Counter

from semantic_lab.domain.records import Product, ProductFlavour
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import planted
from semantic_lab.seed.draw import decimal_from_hundredths

SINGLE_ORIGIN_PRODUCTS = 28
BLEND_PRODUCTS = 10
DECAF_PRODUCTS = 2
MAX_FLAVOUR_NOTES = 3

# A product of one of these categories is made from the lots of one origin region.
ONE_LOT_CATEGORIES = ("category.single-origin", "category.microlot", "category.decaf")
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
BLEND_CATEGORIES = ("category.blend", "category.espresso-blend", "category.filter-blend")
# The name of a one-lot product is its region's label and a suffix. Each category has its own
# suffixes, and a region's products of a category take them in turn, so names never repeat.
NAME_SUFFIXES = {
    "category.single-origin": (
        "Classic",
        "Reserve",
        "Estate",
        "Heritage",
        "Harvest",
        "Select",
        "Signature",
        "Gran Reserva",
    ),
    "category.microlot": ("Microlot", "Microlot Select", "Microlot Reserve", "Microlot Lab"),
    "category.decaf": ("Decaf", "Decaf Reserve"),
}


def generate_products(
    taxonomy: Taxonomy, rng: random.Random, origin_regions: tuple[str, ...]
) -> tuple[tuple[Product, ...], tuple[ProductFlavour, ...]]:
    """The products and their flavour notes.

    The products of each one-lot category go round `origin_regions`, and each one's name starts
    with the English label of its own region.
    """
    regions = list(origin_regions)
    rng.shuffle(regions)
    categories = [
        "category.microlot" if index % 4 == 3 else "category.single-origin"
        for index in range(SINGLE_ORIGIN_PRODUCTS)
    ] + ["category.decaf"] * DECAF_PRODUCTS
    made: Counter[str] = Counter()
    named: list[tuple[str, str, str | None]] = []
    for category in categories:
        # A category's products go round the regions, so its k-th product takes suffix k // len.
        region = regions[made[category] % len(regions)]
        suffix = NAME_SUFFIXES[category][made[category] // len(regions)]
        made[category] += 1
        named.append((f"{taxonomy.get(region).label_en} {suffix}", category, region))
    named.append(("Alba", "category.espresso-blend", None))
    named.append(("Brisa", "category.filter-blend", None))
    for name in BLEND_NAMES[: BLEND_PRODUCTS - len(planted.BLENDS)]:
        named.append((name, rng.choice(BLEND_CATEGORIES), None))
    rng.shuffle(named)
    flavours = [c.key for c in taxonomy.leaves("flavour")]
    products = []
    links = []
    for index, (name, category, origin) in enumerate(named):
        code = f"P-{index + 1:02d}"
        bag_weight = rng.choice((250, 1000))
        price = rng.randint(600, 1400) if bag_weight == 250 else rng.randint(2000, 5000)
        products.append(
            Product(code, name, category, origin, bag_weight, decimal_from_hundredths(price))
        )
        for flavour in sorted(rng.sample(flavours, rng.randint(1, MAX_FLAVOUR_NOTES))):
            links.append(ProductFlavour(code, flavour))
    return tuple(products), tuple(links)
