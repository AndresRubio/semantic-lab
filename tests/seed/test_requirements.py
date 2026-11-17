import pytest

from semantic_lab.domain.errors import GenerationError
from semantic_lab.domain.taxonomy import Concept, Taxonomy, build_taxonomy
from semantic_lab.seed import lots, names, requirements, supply


def concept(key: str, parent: str | None = None) -> Concept:
    scheme = key.split(".")[0]
    return Concept(key, scheme, f"https://example.org/{key}", key, key, (), parent)


def without(taxonomy: Taxonomy, *removed: str) -> Taxonomy:
    return build_taxonomy(c for c in taxonomy.concepts if c.key not in removed)


def plus(taxonomy: Taxonomy, *added: Concept) -> Taxonomy:
    return build_taxonomy([*taxonomy.concepts, *added])


def test_the_real_taxonomy_passes(taxonomy: Taxonomy) -> None:
    requirements.check(taxonomy)


def test_a_process_without_a_weight_is_refused(taxonomy: Taxonomy) -> None:
    with pytest.raises(GenerationError, match=r"process\.carbonic-maceration.*PROCESS_WEIGHTS"):
        requirements.check(plus(taxonomy, concept("process.carbonic-maceration")))


def test_a_weight_for_a_process_that_is_gone_is_refused(taxonomy: Taxonomy) -> None:
    with pytest.raises(GenerationError, match=r"PROCESS_WEIGHTS.*process\.black-honey"):
        requirements.check(without(taxonomy, "process.black-honey"))


def test_a_country_with_a_region_but_no_port_is_refused(taxonomy: Taxonomy) -> None:
    added = (
        concept("geo.chile", "geo.south-america"),
        concept("geo.atacama", "geo.chile"),
    )
    with pytest.raises(GenerationError, match=r"geo\.chile.*ORIGIN_PORTS"):
        requirements.check(plus(taxonomy, *added))


def test_a_country_without_regions_is_refused(taxonomy: Taxonomy) -> None:
    with pytest.raises(GenerationError, match=r"geo\.chile.*depth 1"):
        requirements.check(plus(taxonomy, concept("geo.chile", "geo.south-america")))


def test_a_region_below_a_region_is_refused(taxonomy: Taxonomy) -> None:
    with pytest.raises(GenerationError, match=r"geo\.pitalito.*depth 3"):
        requirements.check(plus(taxonomy, concept("geo.pitalito", "geo.huila")))


def test_a_geo_scheme_with_no_regions_is_refused(taxonomy: Taxonomy) -> None:
    only_geo_roots = [c for c in taxonomy.concepts if c.scheme != "geo"]
    with pytest.raises(GenerationError, match="geo"):
        requirements.check(build_taxonomy(only_geo_roots))


def test_a_removed_category_the_products_use_is_refused(taxonomy: Taxonomy) -> None:
    with pytest.raises(GenerationError, match=r"ONE_LOT_CATEGORIES.*category\.decaf"):
        requirements.check(without(taxonomy, "category.decaf"))


def test_a_removed_blend_category_is_refused(taxonomy: Taxonomy) -> None:
    with pytest.raises(GenerationError, match=r"BLEND_CATEGORIES.*category\.filter-blend"):
        requirements.check(without(taxonomy, "category.filter-blend"))


def test_a_flavour_scheme_with_two_leaves_is_refused(taxonomy: Taxonomy) -> None:
    kept = [c for c in taxonomy.concepts if c.scheme != "flavour"]
    kept += [concept("flavour.sweet"), concept("flavour.sour")]
    with pytest.raises(GenerationError, match=r"flavour.*2 leaves"):
        requirements.check(build_taxonomy(kept))


def test_a_taxonomy_without_the_pool_country_is_refused(taxonomy: Taxonomy) -> None:
    subtree = {c.key for c in taxonomy.descendants("geo.ethiopia")} | {"geo.ethiopia"}
    with pytest.raises(GenerationError, match=r"geo\.ethiopia"):
        requirements.check(without(taxonomy, *subtree))


def test_a_pool_country_that_is_not_a_country_is_refused(
    taxonomy: Taxonomy, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lots, "POOL_COUNTRY", "geo.nowhere")
    with pytest.raises(GenerationError, match=r"POOL_COUNTRY.*geo\.nowhere"):
        requirements.check(taxonomy)


def test_a_port_for_a_country_that_is_not_there_is_refused(
    taxonomy: Taxonomy, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(names.ORIGIN_PORTS, "geo.chile", "Valparaiso")
    with pytest.raises(GenerationError, match=r"ORIGIN_PORTS.*geo\.chile"):
        requirements.check(taxonomy)


def test_a_shipment_plan_that_leaves_too_few_later_shipments_is_refused(
    taxonomy: Taxonomy, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Six countries and 14 shipments give each country 2 at the least, which are the early ones.
    monkeypatch.setattr(supply, "SHIPMENT_COUNT", 14)
    with pytest.raises(GenerationError, match="SHIPMENT_COUNT"):
        requirements.check(taxonomy)
