from pathlib import Path

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from semantic_lab.domain.errors import TaxonomyError
from semantic_lab.domain.taxonomy import Concept, Taxonomy, build_taxonomy


def load_taxonomy(directory: Path) -> Taxonomy:
    """Read every Turtle file in the directory into one graph and build the taxonomy."""
    files = sorted(directory.glob("*.ttl"))
    if not files:
        raise TaxonomyError(f"no Turtle files in {directory}")
    graph = Graph()
    for file in files:
        try:
            graph.parse(file, format="turtle")
        except (SyntaxError, ValueError, IndexError) as error:
            # rdflib's Turtle parser raises BadSyntax (a SyntaxError) for bad syntax, a
            # UnicodeDecodeError (a ValueError) for bytes that are not UTF-8, and a bare
            # IndexError when the text stops in the middle of a statement.
            reason = " ".join(str(error).split()) or type(error).__name__
            raise TaxonomyError(f"{file.name}: not valid Turtle: {reason}") from error
    subjects = sorted(s for s in graph.subjects(RDF.type, SKOS.Concept) if isinstance(s, URIRef))
    concepts = [_concept(graph, subject) for subject in subjects]
    return build_taxonomy(concepts)


def _literals(graph: Graph, subject: URIRef, predicate: URIRef) -> list[Literal]:
    return [o for o in graph.objects(subject, predicate) if isinstance(o, Literal)]


def _one(graph: Graph, subject: URIRef, predicate: URIRef, what: str) -> object:
    values = list(graph.objects(subject, predicate))
    if len(values) != 1:
        raise TaxonomyError(f"concept {subject} has {len(values)} {what}, expected 1")
    return values[0]


def _pref_label(graph: Graph, subject: URIRef, lang: str) -> str:
    labels = [str(o) for o in _literals(graph, subject, SKOS.prefLabel) if o.language == lang]
    if len(labels) != 1:
        raise TaxonomyError(f"concept {subject} has {len(labels)} {lang} prefLabels, expected 1")
    return labels[0]


def _key_of(graph: Graph, subject: URIRef) -> str:
    notation = _one(graph, subject, SKOS.notation, "notations")
    return str(notation)


def _concept(graph: Graph, subject: URIRef) -> Concept:
    key = _key_of(graph, subject)
    scheme_node = _one(graph, subject, SKOS.inScheme, "inScheme links")
    if not isinstance(scheme_node, URIRef):
        raise TaxonomyError(f"concept {subject} has an inScheme that is not a resource")
    scheme = str(_one(graph, scheme_node, SKOS.notation, "scheme notations"))
    broader = list(graph.objects(subject, SKOS.broader))
    if len(broader) > 1:
        raise TaxonomyError(f"concept {subject} has {len(broader)} skos:broader, expected at most 1")
    parent_key: str | None = None
    if broader:
        parent = broader[0]
        if not isinstance(parent, URIRef) or (parent, RDF.type, SKOS.Concept) not in graph:
            raise TaxonomyError(f"concept {subject} has a skos:broader that is not a concept")
        parent_key = _key_of(graph, parent)
    alt_labels = tuple(
        sorted(
            (o.language or "", str(o)) for o in _literals(graph, subject, SKOS.altLabel)
        )
    )
    return Concept(
        key=key,
        scheme=scheme,
        iri=str(subject),
        label_en=_pref_label(graph, subject, "en"),
        label_es=_pref_label(graph, subject, "es"),
        alt_labels=alt_labels,
        parent_key=parent_key,
    )
