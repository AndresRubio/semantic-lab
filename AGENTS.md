# AGENTS.md

semantic-lab is a learning repository: one invented domain (Cumbre Coffee, an importer and
roaster) modelled four ways, as a taxonomy, an ontology, a knowledge graph in Neo4j and a
semantic layer in Cube Core, with an agent on a local Ollama model that answers questions
over them. Units 1 (the skeleton) and 2 (the domain, the seed and the first questions) are built. The design is
`docs/superpowers/specs/2026-11-16-semantic-lab-design.md` and the facts measured against the
running services are in `docs/superpowers/specs/measured-facts.md`. Read `CODING_STANDARDS.md`
before you write code.

## Commands

Run from the repository root. `[writes]` means the command creates or changes files, containers
or volumes. `[read-only]` means it leaves the working tree and the Docker state as they were.

- `cp .env.example .env` [writes]: the owner's first step. `.env` is ignored by git.
- `docker compose up -d` [writes]: starts Postgres, Neo4j and Cube on the development ports
  (5440, 7474, 7687, 4000), bound to 127.0.0.1, with the values from `.env`.
- `uv run --env-file .env python -m semantic_lab.commands.smoke` [read-only]: probes each
  service once and prints one line each. `--no-model` skips Ollama.
- `uv run --env-file .env python -m semantic_lab.commands.seed` [writes]: loads the four
  taxonomies from `ontology/taxonomy/`, generates the dataset and rebuilds the 17 Postgres
  tables in one transaction, then prints each table's row count. `--seed` changes the
  generator's seed and `--taxonomy-dir` the folder of `.ttl` files.
- `uv run --env-file .env python -m semantic_lab.commands.questions` [read-only]: runs the
  reference SQL of each question in `questions/` in a read-only transaction and prints `ok`,
  `DRIFT`, `MISSING` or `ERROR` for each. It exits 1 unless all are `ok`.
- `uv run --env-file .env python -m semantic_lab.commands.questions --write-expected` [writes]:
  writes `questions/expected/<id>.json` from the database instead of checking it.
- `scripts/check.sh` [read-only]: ruff, mypy and the offline suite. It records a pass against
  the hash of the working tree, so a second run on an unchanged tree ends at once, and
  `--force` runs the checks again. The record lives in the git directory.
- `uv run pytest -n auto -m "not db and not model"` [read-only]: the offline suite.
- `uv run pytest -m db` [writes]: starts its own stack under the project name
  `semantic-lab-test` on ports 5441, 7475, 7688 and 4001, and removes it with its volumes
  when it ends. It reads `tests/stack.env` and never needs `.env`. Do not add `-n`. Only one `db`
  run can happen on a machine at a time: every checkout uses the project name
  `semantic-lab-test` and the same ports, so a second run's teardown would remove the first
  run's stack.
- `uv run --env-file .env pytest -m model -q` [read-only]: asks the local model for a tool call.
  It needs Ollama running with the model named in `.env`, and no Docker stack.
- `docker compose down` [writes]: stops the development stack and keeps its data.

## Architecture

Packages that exist today have no mark. Packages marked planned come from the design and a
later unit adds each one.

```
src/semantic_lab/
  config.py        the settings and config.load
  pg.py            opens every Postgres connection, with a timeout and an error with no credential
  probes.py        one probe per service
  redaction.py     one detail line for an exception, with no credential in it
  domain/          records.py (the row types), taxonomy.py (Taxonomy), errors.py: standard library only
  rdf/             taxonomy.py: reads the SKOS files with rdflib into a Taxonomy
  seed/            the seeded generator, schema.sql (17 tables) and load.py (the rebuild)
  evals/           questions.py (the question files) and reference.py (runs a reference query)
  semantic/        token.py: the signed token Cube expects (the client is planned, unit 5)
  commands/        smoke.py, seed.py, questions.py
  graph/           planned, unit 4
  agent/           planned, unit 6
tests/             mirrors src/, plus guards/ (repository checks), support/ and stack.env
cube/model/cubes/  healthcheck.yml, the one cube that lets the smoke probe see Cube answer
compose.yaml       postgres, neo4j, cube
ontology/taxonomy/ the four SKOS files: geo, process, flavour and category (70 concepts)
ontology/          the ontology, the shapes and the mapping are planned, unit 3
questions/         dev.toml (8 questions), heldout.toml (4) and expected/, one JSON answer each
```

`seed/` holds one module per table group (`supply.py`, `lots.py`, `products.py`,
`batches.py`, `orders.py`, `recalls.py`, `sales.py`), `generate.py` that joins them into a
`Dataset`, `requirements.py` that checks a taxonomy before anything is drawn, and `planted.py`,
`names.py` and `draw.py` for the planted facts, the names and the draws. The generator is pure:
the same seed gives the same rows.

A test for a planned layer sits in that layer's future directory. `tests/graph/` holds the
Neo4j read-only check, which tests the driver and the container until `src/semantic_lab/graph/`
exists, and `tests/agent/` holds the model tool-call check until `src/semantic_lab/agent/`
exists.

## When the generator changes

A change to the generator changes the rows, so it changes the pinned digest in
`tests/seed/test_generate.py` and the stored answers in `questions/expected/`.
`tests/evals/test_reference_answers.py` recomputes every stored answer in plain Python from the
in-memory dataset, so it fails until the answers are produced again. A change to the concepts of
a taxonomy (a leaf, a region or a process added, removed or renamed by key) changes the digest and
the answers as well, because the generator draws from them. A change to an alternative label does
not. Moving to another Python minor version can change them in the same way, because the draw
sequence of `random` is not promised across minor versions. Produce the answers against the test
stack, never the development stack, one command per call:

```bash
docker compose -p semantic-lab-test -f compose.yaml --env-file tests/stack.env up -d
uv run --env-file tests/stack.env python -m semantic_lab.commands.smoke --no-model   # repeat until three ok lines
uv run --env-file tests/stack.env python -m semantic_lab.commands.seed
uv run --env-file tests/stack.env python -m semantic_lab.commands.questions --write-expected
docker compose -p semantic-lab-test -f compose.yaml --env-file tests/stack.env down -v
```

Then read each expected file and check it is plausible, copy the new digest from the failing
test into `PINNED`, and run the test ladder.

## Test ladder

Work up the ladder as the change grows:

1. The test file that mirrors the file you changed.
2. The tests of its package.
3. `scripts/check.sh`.
4. Before a pull request, `uv run pytest -n auto -m "not db and not model"` and
   `uv run pytest -m db`.

The test stack and the development stack together need about twice the memory of one
(about 1.7 GiB for the development stack with no data loaded, see the measured facts), so
stop the development stack with `docker compose down` first if the machine is tight.
Other containers on this Mac, such as boe-agent's on 5433 and 5434, are not ours: leave them.

## Rules that bind every change

- Python 3.13, managed with `uv`. Never `pip`.
- Every address, port and credential comes from the environment. No default lives in code.
- Commit on a branch, one plain sentence as the message. Do not use `--no-verify`.
