# semantic-lab

A lab for learning four things by building them over the same data: a taxonomy (SKOS), an
ontology (RDFS/OWL with SHACL), a knowledge graph (Neo4j) and a semantic layer (Cube Core). An
agent on a local Ollama model answers questions in plain language, and the tools it holds are
a setting, so the same question can be asked with Cube, without it, with the graph, or with
everything. An evaluation scores each combination against known answers.

The data is invented: Cumbre Coffee, an importer and roaster that buys lots from cooperatives
and sells bags to cafés.

## Status

Nothing runs yet. The design is in
[`docs/superpowers/specs/2026-11-16-semantic-lab-design.md`](docs/superpowers/specs/2026-11-16-semantic-lab-design.md),
and the work is split into seven units listed there under "Order of work".

## Licence

MIT. See [`LICENSE`](LICENSE).
