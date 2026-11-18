import random

import pytest

from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.seed.sales import generate_sales
from semantic_lab.seed.supply import Supply, generate_supply
from tests.support.seed import SEEDS, World


@pytest.fixture(scope="session", params=SEEDS)
def world(request: pytest.FixtureRequest, taxonomy: Taxonomy) -> World:
    rng = random.Random(request.param)
    supply = generate_supply(taxonomy, rng)
    return World(supply, generate_sales(supply, rng))


@pytest.fixture
def supply(world: World) -> Supply:
    return world.supply
