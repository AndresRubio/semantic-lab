import random
from pathlib import Path

import pytest

from semantic_lab.domain.records import Dataset
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.rdf.taxonomy import load_taxonomy
from semantic_lab.seed import generate
from semantic_lab.seed.sales import generate_sales
from semantic_lab.seed.supply import Supply, generate_supply
from tests.support.seed import SEEDS, World

DIRECTORY = Path(__file__).resolve().parent.parent.parent / "ontology" / "taxonomy"


@pytest.fixture(scope="session")
def taxonomy() -> Taxonomy:
    return load_taxonomy(DIRECTORY)


@pytest.fixture(scope="session")
def dataset(taxonomy: Taxonomy) -> Dataset:
    return generate.generate(taxonomy, generate.DEFAULT_SEED)


@pytest.fixture(scope="session", params=SEEDS)
def world(request: pytest.FixtureRequest, taxonomy: Taxonomy) -> World:
    rng = random.Random(request.param)
    supply = generate_supply(taxonomy, rng)
    return World(supply, generate_sales(supply, rng))


@pytest.fixture
def supply(world: World) -> Supply:
    return world.supply
