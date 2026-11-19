# semantic-lab

A lab for learning four things by building them over the same data: a taxonomy (SKOS), an
ontology (RDFS/OWL with SHACL), a knowledge graph (Neo4j) and a semantic layer (Cube Core). An
agent on a local Ollama model answers questions in plain language, and the tools it holds are
a setting, so the same question can be asked with Cube, without it, with the graph, or with
everything. An evaluation scores each combination against known answers.

The data is invented: Cumbre Coffee, an importer and roaster that buys lots from cooperatives
and sells bags to cafés.

## Status

Units 1 to 3 are built. `docker compose up -d` starts Postgres, Neo4j and Cube on the
development ports, and a smoke command checks that each one answers. A seeded generator
produces the Cumbre Coffee dataset (15 cooperatives, 600 lots, 20,000 orders and 60,000 order
lines), and `python -m semantic_lab.commands.seed` loads it into Postgres along with the four
SKOS taxonomies in `ontology/taxonomy/`. Twelve questions in `questions/` (eight for
development, four held out) each carry reference SQL and a stored answer, and
`python -m semantic_lab.commands.questions` checks them against the database. The design is in
[`docs/superpowers/specs/2026-11-16-semantic-lab-design.md`](docs/superpowers/specs/2026-11-16-semantic-lab-design.md),
and what was measured against the running services is in
[`docs/superpowers/specs/measured-facts.md`](docs/superpowers/specs/measured-facts.md).

`ontology/` also holds `ontology.ttl` (14 classes and their properties), `shapes.ttl` (the SHACL
shapes for the taxonomies, the ontology and the data) and `mapping.yaml`, which says which
Postgres table and column each ontology term comes from. `python -m
semantic_lab.commands.ontology` checks the three against each other and against the generator's
rows exported as RDF, with no database.

Four units remain, from "Order of work" in the design: the knowledge graph (4), the semantic
layer (5), the agent (6) and the evaluation (7).

## Licence

MIT. See [`LICENSE`](LICENSE).
