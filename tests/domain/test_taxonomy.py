import pytest

from semantic_lab.domain.errors import TaxonomyError
from semantic_lab.domain.taxonomy import Concept, build_taxonomy


def concept(
    key: str,
    parent_key: str | None = None,
    scheme: str = "t",
    label_en: str = "en",
    label_es: str = "es",
) -> Concept:
    slug = key.split(".", 1)[-1]
    return Concept(
        key=key,
        scheme=scheme,
        iri=f"https://example.test/{scheme}#{slug}",
        label_en=label_en,
        label_es=label_es,
        alt_labels=(),
        parent_key=parent_key,
    )


def sample() -> list[Concept]:
    # a > b > c, a > d
    return [
        concept("t.d", "t.a"),
        concept("t.c", "t.b"),
        concept("t.a"),
        concept("t.b", "t.a"),
    ]


def keys(concepts: tuple[Concept, ...]) -> tuple[str, ...]:
    return tuple(c.key for c in concepts)


def test_concepts_come_back_sorted_by_key() -> None:
    assert keys(build_taxonomy(sample()).concepts) == ("t.a", "t.b", "t.c", "t.d")


def test_children_descendants_and_leaves() -> None:
    taxonomy = build_taxonomy(sample())
    assert keys(taxonomy.children("t.a")) == ("t.b", "t.d")
    assert keys(taxonomy.descendants("t.a")) == ("t.b", "t.c", "t.d")
    assert keys(taxonomy.leaves("t")) == ("t.c", "t.d")
    assert keys(taxonomy.in_scheme("t")) == ("t.a", "t.b", "t.c", "t.d")
    assert taxonomy.in_scheme("other") == ()


def test_closure_pairs_each_concept_with_itself_and_its_ancestors() -> None:
    assert build_taxonomy(sample()).closure() == (
        ("t.a", "t.a", 0),
        ("t.a", "t.b", 1),
        ("t.a", "t.c", 2),
        ("t.a", "t.d", 1),
        ("t.b", "t.b", 0),
        ("t.b", "t.c", 1),
        ("t.c", "t.c", 0),
        ("t.d", "t.d", 0),
    )


def test_get_of_an_unknown_key_raises_taxonomy_error() -> None:
    with pytest.raises(TaxonomyError, match="t.zzz"):
        build_taxonomy(sample()).get("t.zzz")
    assert build_taxonomy(sample()).get("t.b").key == "t.b"


CASES = {
    "duplicate key": ([concept("t.a"), concept("t.a")], "t.a"),
    "parent not present": ([concept("t.a", "t.missing")], "t.missing"),
    "parent in another scheme": (
        [concept("u.p", scheme="u"), concept("t.a", "u.p")],
        "u.p",
    ),
    "cycle": ([concept("t.a", "t.b"), concept("t.b", "t.a")], "t.a"),
    "empty label_en": ([concept("t.a", label_en="")], "t.a"),
    "empty label_es": ([concept("t.a", label_es="")], "t.a"),
    "key without scheme prefix": ([concept("x.a", scheme="t")], "x.a"),
}


@pytest.mark.parametrize("case", CASES)
def test_build_refuses(case: str) -> None:
    concepts, named = CASES[case]
    with pytest.raises(TaxonomyError, match=named):
        build_taxonomy(concepts)
