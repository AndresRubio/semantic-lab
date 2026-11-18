from collections import Counter
from pathlib import Path

import pytest

from semantic_lab.domain.errors import TaxonomyError
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.rdf.taxonomy import load_taxonomy

ROOT = Path(__file__).resolve().parent.parent.parent
DIRECTORY = ROOT / "ontology" / "taxonomy"
BASE = "https://semantic-lab.example/taxonomy/"


@pytest.fixture(scope="module")
def taxonomy() -> Taxonomy:
    return load_taxonomy(DIRECTORY)


def test_the_four_files_load_to_70_concepts(taxonomy: Taxonomy) -> None:
    assert len(taxonomy.concepts) == 70
    assert Counter(c.scheme for c in taxonomy.concepts) == {
        "geo": 33,
        "process": 7,
        "flavour": 23,
        "category": 7,
    }


def test_the_pinned_labels(taxonomy: Taxonomy) -> None:
    washed = taxonomy.get("process.washed")
    assert (washed.label_en, washed.label_es) == ("Washed", "Lavado")
    assert ("en", "wet process") in washed.alt_labels
    assert ("en", "dry process") in taxonomy.get("process.natural").alt_labels
    assert taxonomy.get("flavour.fruity").label_es == "Afrutado"
    narino = taxonomy.get("geo.narino")
    assert (narino.label_en, narino.label_es) == ("Nariño", "Nariño")


def test_every_iri_is_built_from_its_key(taxonomy: Taxonomy) -> None:
    for c in taxonomy.concepts:
        scheme, slug = c.key.split(".", 1)
        assert c.iri == f"{BASE}{scheme}#{slug}"
    assert taxonomy.get("process.red-honey").iri == f"{BASE}process#red-honey"


def test_fruity_reaches_its_eight_descendants(taxonomy: Taxonomy) -> None:
    assert [c.key for c in taxonomy.descendants("flavour.fruity")] == sorted(
        f"flavour.{s}"
        for s in (
            "berry",
            "blackberry",
            "raspberry",
            "citrus",
            "orange",
            "lemon",
            "stone-fruit",
            "peach",
        )
    )


def test_every_region_has_a_country_and_a_continent(taxonomy: Taxonomy) -> None:
    leaves = taxonomy.leaves("geo")
    assert len(leaves) == 24
    depth_of = {(a, d): depth for a, d, depth in taxonomy.closure()}
    for leaf in leaves:
        depths = sorted(
            depth
            for (ancestor, descendant), depth in depth_of.items()
            if descendant == leaf.key and depth > 0
        )
        assert depths == [1, 2]


GOOD = f"""@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
<{BASE}t> a skos:ConceptScheme ; skos:notation "t" .
"""
IRI = f"{BASE}t#a"
FAULTS = {
    "no es prefLabel": f"""<{IRI}> a skos:Concept ; skos:notation "t.a" ;
        skos:prefLabel "A"@en ; skos:inScheme <{BASE}t> .""",
    "two en prefLabels": f"""<{IRI}> a skos:Concept ; skos:notation "t.a" ;
        skos:prefLabel "A"@en, "B"@en, "A"@es ; skos:inScheme <{BASE}t> .""",
    "no notation": f"""<{IRI}> a skos:Concept ;
        skos:prefLabel "A"@en, "A"@es ; skos:inScheme <{BASE}t> .""",
    "two broader": f"""<{BASE}t#b> a skos:Concept ; skos:notation "t.b" ;
        skos:prefLabel "B"@en, "B"@es ; skos:inScheme <{BASE}t> .
        <{BASE}t#c> a skos:Concept ; skos:notation "t.c" ;
        skos:prefLabel "C"@en, "C"@es ; skos:inScheme <{BASE}t> .
        <{IRI}> a skos:Concept ; skos:notation "t.a" ;
        skos:prefLabel "A"@en, "A"@es ; skos:inScheme <{BASE}t> ;
        skos:broader <{BASE}t#b>, <{BASE}t#c> .""",
    "broader points at no concept": f"""<{IRI}> a skos:Concept ; skos:notation "t.a" ;
        skos:prefLabel "A"@en, "A"@es ; skos:inScheme <{BASE}t> ;
        skos:broader <{BASE}t#ghost> .""",
    "no inScheme": f"""<{IRI}> a skos:Concept ; skos:notation "t.a" ;
        skos:prefLabel "A"@en, "A"@es .""",
}


@pytest.mark.parametrize("case", FAULTS)
def test_a_broken_file_is_refused(case: str, tmp_path: Path) -> None:
    (tmp_path / "t.ttl").write_text(GOOD + FAULTS[case])
    with pytest.raises(TaxonomyError, match=IRI.replace(".", r"\.")):
        load_taxonomy(tmp_path)


def test_a_good_file_loads(tmp_path: Path) -> None:
    good = f"""<{IRI}> a skos:Concept ; skos:notation "t.a" ;
        skos:prefLabel "A"@en, "A"@es ; skos:inScheme <{BASE}t> ."""
    (tmp_path / "t.ttl").write_text(GOOD + good)
    assert [c.key for c in load_taxonomy(tmp_path).concepts] == ["t.a"]


def test_an_empty_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(TaxonomyError):
        load_taxonomy(tmp_path)


def test_a_file_with_a_syntax_error_is_refused_and_named(tmp_path: Path) -> None:
    (tmp_path / "good.ttl").write_text(GOOD)
    (tmp_path / "broken.ttl").write_text("this is not turtle {{{")
    with pytest.raises(TaxonomyError, match=r"broken\.ttl") as refused:
        load_taxonomy(tmp_path)
    assert "\n" not in str(refused.value)
    assert str(tmp_path) not in str(refused.value)


def test_a_file_that_is_not_text_is_refused(tmp_path: Path) -> None:
    (tmp_path / "binary.ttl").write_bytes(b"\xff\xfe\x00\x80 garbage \xff")
    with pytest.raises(TaxonomyError, match=r"binary\.ttl"):
        load_taxonomy(tmp_path)


def test_a_truncated_file_is_refused(tmp_path: Path) -> None:
    (tmp_path / "cut.ttl").write_text("@prefix a: <x> .\n a:b a:c")
    with pytest.raises(TaxonomyError, match=r"cut\.ttl"):
        load_taxonomy(tmp_path)
