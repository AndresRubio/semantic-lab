from pathlib import Path

from rdflib import Graph, URIRef
from rdflib.namespace import OWL, RDF, RDFS

from semantic_lab.domain.errors import OntologyError
from semantic_lab.domain.ontology import OntologyClass, Ontology, Property, build_ontology
from semantic_lab.rdf import turtle


def ontology_graph(file: Path) -> Graph:
    """Read the ontology's Turtle file into a graph."""
    return turtle.read([file], OntologyError)


def ontology_of(graph: Graph) -> Ontology:
    """Build the ontology from the OWL classes and properties of a graph."""
    classes = [
        OntologyClass(str(s), _parent(graph, s)) for s in _subjects(graph, OWL.Class)
    ]
    properties = [
        Property(str(s), "object", _domain(graph, s), _range(graph, s))
        for s in _subjects(graph, OWL.ObjectProperty)
    ] + [
        Property(str(s), "datatype", _domain(graph, s), _range(graph, s))
        for s in _subjects(graph, OWL.DatatypeProperty)
    ]
    return build_ontology(classes, properties)


def _subjects(graph: Graph, owl_type: URIRef) -> list[URIRef]:
    return sorted(s for s in graph.subjects(RDF.type, owl_type) if isinstance(s, URIRef))


def _uri_objects(graph: Graph, subject: URIRef, predicate: URIRef, what: str) -> list[str]:
    values = list(graph.objects(subject, predicate))
    if not all(isinstance(v, URIRef) for v in values):
        raise OntologyError(f"term {subject} has a {what} that is not a resource")
    return [str(v) for v in values]


def _parent(graph: Graph, subject: URIRef) -> str | None:
    parents = _uri_objects(graph, subject, RDFS.subClassOf, "rdfs:subClassOf")
    if len(parents) > 1:
        raise OntologyError(f"class {subject} has {len(parents)} rdfs:subClassOf, expected at most 1")
    return parents[0] if parents else None


def _domain(graph: Graph, subject: URIRef) -> str | None:
    domains = _uri_objects(graph, subject, RDFS.domain, "rdfs:domain")
    if len(domains) > 1:
        raise OntologyError(f"property {subject} has {len(domains)} rdfs:domain, expected at most 1")
    return domains[0] if domains else None


def _range(graph: Graph, subject: URIRef) -> str:
    ranges = _uri_objects(graph, subject, RDFS.range, "rdfs:range")
    if len(ranges) != 1:
        raise OntologyError(f"property {subject} has {len(ranges)} rdfs:range, expected 1")
    return ranges[0]
