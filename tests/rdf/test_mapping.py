from pathlib import Path

import pytest

from semantic_lab.domain.errors import MappingError
from semantic_lab.domain.mapping import (
    ClassEntry,
    Condition,
    Link,
    Mapping,
    PropertyEntry,
    problems,
)
from semantic_lab.domain.ontology import NAMESPACE as SL
from semantic_lab.domain.ontology import Ontology
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.rdf.mapping import load_mapping

GOOD_CLASS = "sl:A:\n    postgres: {table: farm, key: [code]}\n"
GOOD_PROPERTY = "sl:p:\n    postgres: {columns: [farm.name]}\n"


def document(classes: str = GOOD_CLASS, properties: str = GOOD_PROPERTY) -> str:
    def indent(text: str) -> str:
        return "".join("  " + line + "\n" for line in text.splitlines())

    return f"classes:\n{indent(classes)}properties:\n{indent(properties)}"


def class_entry(postgres: str) -> str:
    return f"sl:A:\n  postgres: {postgres}\n"


def property_entry(postgres: str) -> str:
    return f"sl:p:\n  postgres: {postgres}\n"


REFUSALS = {
    "not YAML": ("classes: [unclosed\nproperties: {", "is not YAML"),
    "top level is a list": ("- classes\n- properties\n", "top level"),
    "a term twice": (
        document(properties=GOOD_PROPERTY + GOOD_PROPERTY),
        "the key 'sl:p' appears twice, on line 7",
    ),
    "a key of an entry twice": (
        document(classes="sl:A:\n  postgres: {table: farm, table: lot, key: [code]}\n"),
        "the key 'table' appears twice, on line 3",
    ),
    "a section twice": (
        "classes: {}\nproperties: {}\nclasses: {}\n",
        "the key 'classes' appears twice, on line 3",
    ),
    "no properties key": ("classes: {}\n", "the top level has no properties"),
    "no classes key": ("properties: {}\n", "the top level has no classes"),
    "a third top-level key": (
        "classes: {}\nproperties: {}\nextra: {}\n",
        "the top level has the unknown key 'extra'",
    ),
    "classes is a list": ("classes: [a]\nproperties: {}\n", "classes must be a mapping"),
    "class term without the prefix": (
        document(classes="A:\n  postgres: {table: farm, key: [code]}\n"),
        "term 'A' does not start with sl:",
    ),
    "property term with another prefix": (
        document(properties="ex:p:\n  postgres: {columns: [farm.name]}\n"),
        "term 'ex:p' does not start with sl:",
    ),
    "class entry without postgres": (document(classes="sl:A: {}\n"), "class sl:A has no postgres"),
    "property entry without postgres": (
        document(properties="sl:p: {}\n"),
        "property sl:p has no postgres",
    ),
    "unknown key in a class entry": (
        document(classes="sl:A:\n  postgres: {table: farm, key: [code]}\n  extra: 1\n"),
        "unknown key 'extra'",
    ),
    "unknown key in a class postgres": (
        document(classes=class_entry("{table: farm, key: [code], extra: 1}")),
        "unknown key 'extra'",
    ),
    "unknown key in a when": (
        document(
            classes=class_entry("{table: farm, key: [code], when: {column: c, under: [k], x: 1}}")
        ),
        "unknown key 'x'",
    ),
    "unknown key in a property postgres": (
        document(properties=property_entry("{columns: [farm.name], extra: 1}")),
        "unknown key 'extra'",
    ),
    "unknown key in a link": (
        document(properties=property_entry("{link: {table: t, from: a, to: b, extra: 1}}")),
        "unknown key 'extra'",
    ),
    "unknown key alone in a property postgres": (
        document(properties=property_entry("{extra: 1}")),
        "unknown key 'extra'",
    ),
    "class without a table": (
        document(classes=class_entry("{key: [code]}")),
        "class sl:A: postgres has no table",
    ),
    "class without a key": (
        document(classes=class_entry("{table: farm}")),
        "class sl:A: postgres has no key",
    ),
    "key is a string": (
        document(classes=class_entry("{table: farm, key: code}")),
        "key must be a non-empty list of strings",
    ),
    "key is empty": (
        document(classes=class_entry("{table: farm, key: []}")),
        "key must be a non-empty list of strings",
    ),
    "key holds a number": (
        document(classes=class_entry("{table: farm, key: [1]}")),
        "key must be a non-empty list of strings",
    ),
    "when without under": (
        document(classes=class_entry("{table: farm, key: [code], when: {column: c}}")),
        "when has no under",
    ),
    "when under is empty": (
        document(classes=class_entry("{table: farm, key: [code], when: {column: c, under: []}}")),
        "when.under must be a non-empty list of strings",
    ),
    "column without a dot": (
        document(properties=property_entry("{columns: [farm]}")),
        "'farm' is not of the form table.column",
    ),
    "column with two dots": (
        document(properties=property_entry("{columns: [farm.a.b]}")),
        "'farm.a.b' is not of the form table.column",
    ),
    "column with no table": (
        document(properties=property_entry("{columns: [.name]}")),
        "'.name' is not of the form table.column",
    ),
    "columns is a string": (
        document(properties=property_entry("{columns: farm.name}")),
        "columns must be a non-empty list of strings",
    ),
    "columns and link together": (
        document(
            properties=property_entry(
                "{columns: [farm.name], link: {table: t, from: a, to: b}}"
            )
        ),
        "exactly one of columns and link",
    ),
    "neither columns nor link": (
        document(properties=property_entry("{}")),
        "exactly one of columns and link",
    ),
    "link without a to": (
        document(properties=property_entry("{link: {table: t, from: a}}")),
        "link has no to",
    ),
}


@pytest.mark.parametrize("case", REFUSALS)
def test_a_broken_file_is_refused_in_one_line(case: str, tmp_path: Path) -> None:
    text, named = REFUSALS[case]
    file = tmp_path / "broken.yaml"
    file.write_text(text)
    with pytest.raises(MappingError) as raised:
        load_mapping(file)
    message = str(raised.value)
    assert message.startswith("broken.yaml: ")
    assert "\n" not in message
    assert named in message


def test_a_file_that_is_not_utf_8_is_refused_in_one_line(tmp_path: Path) -> None:
    file = tmp_path / "latin.yaml"
    file.write_bytes(document().encode("utf-8") + "# caf\u00e9\n".encode("latin-1"))
    with pytest.raises(MappingError, match=r"^latin\.yaml: is not UTF-8[^\n]*$"):
        load_mapping(file)


def test_a_missing_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(MappingError, match=r"^nope\.yaml: "):
        load_mapping(tmp_path / "nope.yaml")


def test_a_good_file_loads_with_expanded_terms_sorted_by_iri(tmp_path: Path) -> None:
    file = tmp_path / "good.yaml"
    file.write_text(
        document(
            classes=(
                "sl:B:\n  postgres:\n    table: product\n    key: [code]\n"
                "    when: {column: category_key, under: [category.single-origin, category.decaf]}\n"
                + GOOD_CLASS
            ),
            properties=(
                "sl:q:\n  postgres: {link: {table: lot_farm, from: lot_code, to: farm_code}}\n"
                + GOOD_PROPERTY
            ),
        )
    )
    assert load_mapping(file) == Mapping(
        classes=(
            ClassEntry(SL + "A", "farm", ("code",), None),
            ClassEntry(
                SL + "B",
                "product",
                ("code",),
                Condition("category_key", ("category.decaf", "category.single-origin")),
            ),
        ),
        properties=(
            PropertyEntry(SL + "p", (("farm", "name"),), None),
            PropertyEntry(SL + "q", (), Link("lot_farm", "lot_code", "farm_code")),
        ),
    )


def test_the_file_maps_every_term_and_every_column(
    mapping: Mapping, ontology: Ontology, taxonomy: Taxonomy
) -> None:
    assert problems(mapping, ontology, taxonomy) == ()
    assert (len(mapping.classes), len(mapping.properties)) == (14, 50)
    assert len(mapping.postgres_columns()) == 63


def test_the_two_conditional_classes(mapping: Mapping) -> None:
    conditions = {c.iri: c.when for c in mapping.classes if c.when}
    assert conditions == {
        SL + "Blend": Condition("category_key", ("category.blend",)),
        SL + "SingleLotProduct": Condition(
            "category_key", ("category.decaf", "category.single-origin")
        ),
    }
