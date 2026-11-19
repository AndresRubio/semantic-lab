"""Where the repository's ontology files are, for conftest and for the support modules."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TAXONOMY_DIRECTORY = ROOT / "ontology" / "taxonomy"
ONTOLOGY_FILE = ROOT / "ontology" / "ontology.ttl"
SHAPES_FILE = ROOT / "ontology" / "shapes.ttl"
MAPPING_FILE = ROOT / "ontology" / "mapping.yaml"
