# semantic-lab

A lab for learning four things by building them over the same data: a taxonomy (SKOS), an
ontology (RDFS/OWL with SHACL), a knowledge graph (Neo4j) and a semantic layer (Cube Core). An
agent on a local Ollama model answers questions in plain language, and the tools it holds are
a setting, so the same question can be asked with Cube, without it, with the graph, or with
everything. An evaluation scores each combination against known answers.

The data is invented: Cumbre Coffee, an importer and roaster that buys lots from cooperatives
and sells bags to cafés.

## Status

Unit 1, the skeleton, is built. `docker compose up -d` starts Postgres, Neo4j and Cube on the
development ports, and a smoke command checks that each one answers. The design is in
[`docs/superpowers/specs/2026-11-16-semantic-lab-design.md`](docs/superpowers/specs/2026-11-16-semantic-lab-design.md),
and what was measured against the running services is in
[`docs/superpowers/specs/measured-facts.md`](docs/superpowers/specs/measured-facts.md).

Six units remain, from "Order of work" in the design: the domain and seed (2), the taxonomy and
ontology (3), the knowledge graph (4), the semantic layer (5), the agent (6) and the
evaluation (7).

## Licence

MIT. See [`LICENSE`](LICENSE).
