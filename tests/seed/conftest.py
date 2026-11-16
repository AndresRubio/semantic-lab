from pathlib import Path

import pytest

from semantic_lab.domain.records import Dataset
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.rdf.taxonomy import load_taxonomy
from semantic_lab.seed import generate

DIRECTORY = Path(__file__).resolve().parent.parent.parent / "ontology" / "taxonomy"


@pytest.fixture(scope="session")
def taxonomy() -> Taxonomy:
    return load_taxonomy(DIRECTORY)


@pytest.fixture(scope="session")
def dataset(taxonomy: Taxonomy) -> Dataset:
    return generate.generate(taxonomy, generate.DEFAULT_SEED)
