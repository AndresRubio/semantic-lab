from pathlib import Path

import pytest

from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.rdf.taxonomy import load_taxonomy

DIRECTORY = Path(__file__).resolve().parent.parent.parent / "ontology" / "taxonomy"


@pytest.fixture(scope="session")
def taxonomy() -> Taxonomy:
    return load_taxonomy(DIRECTORY)
