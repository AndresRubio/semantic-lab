from collections.abc import Iterable
from dataclasses import dataclass

from semantic_lab.domain.errors import TaxonomyError


@dataclass(frozen=True)
class Concept:
    key: str
    scheme: str
    iri: str
    label_en: str
    label_es: str
    alt_labels: tuple[tuple[str, str], ...]
    parent_key: str | None


@dataclass(frozen=True)
class Taxonomy:
    concepts: tuple[Concept, ...]

    def get(self, key: str) -> Concept:
        for concept in self.concepts:
            if concept.key == key:
                return concept
        raise TaxonomyError(f"unknown concept key {key}")

    def children(self, key: str) -> tuple[Concept, ...]:
        self.get(key)
        return tuple(c for c in self.concepts if c.parent_key == key)

    def descendants(self, key: str) -> tuple[Concept, ...]:
        found: list[Concept] = []
        pending = list(self.children(key))
        while pending:
            concept = pending.pop()
            found.append(concept)
            pending.extend(self.children(concept.key))
        return tuple(sorted(found, key=lambda c: c.key))

    def in_scheme(self, scheme: str) -> tuple[Concept, ...]:
        return tuple(c for c in self.concepts if c.scheme == scheme)

    def leaves(self, scheme: str) -> tuple[Concept, ...]:
        parents = {c.parent_key for c in self.concepts}
        return tuple(c for c in self.in_scheme(scheme) if c.key not in parents)

    def closure(self) -> tuple[tuple[str, str, int], ...]:
        """Every (ancestor, descendant, depth) pair, each concept paired with itself at depth 0."""
        rows: list[tuple[str, str, int]] = []
        for concept in self.concepts:
            ancestor: Concept | None = concept
            depth = 0
            while ancestor is not None:
                rows.append((ancestor.key, concept.key, depth))
                ancestor = self.get(ancestor.parent_key) if ancestor.parent_key else None
                depth += 1
        return tuple(sorted(rows))


def build_taxonomy(concepts: Iterable[Concept]) -> Taxonomy:
    ordered = tuple(sorted(concepts, key=lambda c: c.key))
    by_key: dict[str, Concept] = {}
    for concept in ordered:
        if concept.key in by_key:
            raise TaxonomyError(f"duplicate concept key {concept.key}")
        by_key[concept.key] = concept
    for concept in ordered:
        if not concept.label_en or not concept.label_es:
            raise TaxonomyError(f"concept {concept.key} has an empty label")
        if not concept.key.startswith(f"{concept.scheme}."):
            raise TaxonomyError(
                f"concept key {concept.key} does not start with {concept.scheme}."
            )
        if concept.parent_key is None:
            continue
        parent = by_key.get(concept.parent_key)
        if parent is None:
            raise TaxonomyError(
                f"concept {concept.key} has parent {concept.parent_key}, which is not present"
            )
        if parent.scheme != concept.scheme:
            raise TaxonomyError(
                f"concept {concept.key} has parent {parent.key} in scheme {parent.scheme}"
            )
    for concept in ordered:
        seen = {concept.key}
        current = concept
        while current.parent_key is not None:
            current = by_key[current.parent_key]
            if current.key in seen:
                raise TaxonomyError(f"concept {concept.key} is part of a cycle")
            seen.add(current.key)
    return Taxonomy(concepts=ordered)
