"""What the generator needs from a taxonomy, checked once before anything is drawn.

The generator keeps tables keyed by concept (processing weights, origin ports, category lists)
and assumes the shape of the geo scheme. A taxonomy that no longer fits them fails here with
one `GenerationError` that names the concept or the table, where it would otherwise fail deep
inside a draw with a `KeyError`.
"""

from semantic_lab.domain.errors import GenerationError
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed import lots, names, products, supply

# A country sails its early shipments first and then at least this many more, spread over the
# later departure window.
MIN_LATER_SHIPMENTS = 2
# Continent, country, region: a region has two ancestors.
REGION_DEPTH = 2


def check(taxonomy: Taxonomy) -> None:
    """Raise `GenerationError` for the first thing the generator cannot build from."""
    _processes(taxonomy)
    countries = _countries(taxonomy)
    _ports(countries)
    _pool_country(countries)
    _categories(taxonomy)
    _flavours(taxonomy)
    _shipment_plan(countries)


def _processes(taxonomy: Taxonomy) -> None:
    keys = {c.key for c in taxonomy.in_scheme("process")}
    for key in sorted(keys - set(lots.PROCESS_WEIGHTS)):
        raise GenerationError(f"process concept {key} has no weight in PROCESS_WEIGHTS")
    for key in sorted(set(lots.PROCESS_WEIGHTS) - keys):
        raise GenerationError(f"PROCESS_WEIGHTS names {key}, which is not a process concept")


def _depth(taxonomy: Taxonomy, key: str) -> int:
    depth = 0
    parent = taxonomy.get(key).parent_key
    while parent is not None:
        depth += 1
        parent = taxonomy.get(parent).parent_key
    return depth


def _countries(taxonomy: Taxonomy) -> set[str]:
    """The countries of the geo scheme, after checking that every leaf is a region."""
    leaves = taxonomy.leaves("geo")
    if not leaves:
        raise GenerationError("the geo scheme has no regions")
    countries = set()
    for leaf in leaves:
        depth = _depth(taxonomy, leaf.key)
        if depth != REGION_DEPTH or leaf.parent_key is None:
            raise GenerationError(
                f"geo leaf {leaf.key} is at depth {depth}, and the generator needs regions at "
                f"depth {REGION_DEPTH} (continent, country, region)"
            )
        countries.add(leaf.parent_key)
    return countries


def _ports(countries: set[str]) -> None:
    for country in sorted(countries - set(names.ORIGIN_PORTS)):
        raise GenerationError(f"country {country} has no origin port in ORIGIN_PORTS")
    for country in sorted(set(names.ORIGIN_PORTS) - countries):
        raise GenerationError(f"ORIGIN_PORTS names {country}, which is not a country with regions")


def _pool_country(countries: set[str]) -> None:
    if lots.POOL_COUNTRY not in countries:
        raise GenerationError(
            f"POOL_COUNTRY {lots.POOL_COUNTRY} is not a country with regions in the geo scheme"
        )


def _categories(taxonomy: Taxonomy) -> None:
    keys = {c.key for c in taxonomy.in_scheme("category")}
    for table, wanted in (
        ("ONE_LOT_CATEGORIES", products.ONE_LOT_CATEGORIES),
        ("BLEND_CATEGORIES", products.BLEND_CATEGORIES),
    ):
        for key in wanted:
            if key not in keys:
                raise GenerationError(f"{table} names {key}, which is not in the category scheme")


def _flavours(taxonomy: Taxonomy) -> None:
    leaves = len(taxonomy.leaves("flavour"))
    if leaves < products.MAX_FLAVOUR_NOTES:
        raise GenerationError(
            f"the flavour scheme has {leaves} leaves and a product can take "
            f"{products.MAX_FLAVOUR_NOTES} notes"
        )


def _shipment_plan(countries: set[str]) -> None:
    fewest = supply.SHIPMENT_COUNT // len(countries)
    later = fewest - lots.EARLY_SHIPMENTS_PER_COUNTRY
    if later < MIN_LATER_SHIPMENTS:
        raise GenerationError(
            f"SHIPMENT_COUNT {supply.SHIPMENT_COUNT} gives a country of {len(countries)} "
            f"{fewest} shipments, and {lots.EARLY_SHIPMENTS_PER_COUNTRY} of them are early, "
            f"which leaves {later} where the plan needs at least {MIN_LATER_SHIPMENTS}"
        )
