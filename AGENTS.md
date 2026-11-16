# AGENTS.md

semantic-lab is a learning repository: one invented domain (Cumbre Coffee, an importer and
roaster) modelled four ways, as a taxonomy, an ontology, a knowledge graph in Neo4j and a
semantic layer in Cube Core, with an agent on a local Ollama model that answers questions
over them. Only unit 1, the skeleton, is built. The design is
`docs/superpowers/specs/2026-11-16-semantic-lab-design.md` and the facts measured against the
running services are in `docs/superpowers/specs/measured-facts.md`. Read `CODING_STANDARDS.md`
before you write code.

## Commands

Run from the repository root. `[writes]` means the command creates or changes files, containers
or volumes. `[read-only]` means it leaves the repository and the Docker state as they were.

- `cp .env.example .env` [writes]: the owner's first step. `.env` is ignored by git.
- `docker compose up -d` [writes]: starts Postgres, Neo4j and Cube on the development ports
  (5440, 7474, 7687, 4000), bound to 127.0.0.1, with the values from `.env`.
- `uv run --env-file .env python -m semantic_lab.commands.smoke` [read-only]: probes each
  service once and prints one line each. `--no-model` skips Ollama.
- `scripts/check.sh` [read-only]: ruff, mypy and the offline suite. It records a pass against
  the hash of the working tree, so a second run on an unchanged tree ends at once, and
  `--force` runs the checks again. The record lives in the git directory.
- `uv run pytest -n auto -m "not db and not model"` [read-only]: the offline suite.
- `uv run pytest -m db` [writes]: starts its own stack under the project name
  `semantic-lab-test` on ports 5441, 7475, 7688 and 4001, and removes it with its volumes
  when it ends. It reads `tests/stack.env` and never needs `.env`. Do not add `-n`.
- `uv run --env-file .env pytest -m model -q` [read-only]: asks the local model for a tool call.
  It needs Ollama running with the model named in `.env`, and no Docker stack.
- `docker compose down` [writes]: stops the development stack and keeps its data.

## Architecture

Packages that exist today have no mark. Packages marked planned come from the design and a
later unit adds each one.

```
src/semantic_lab/
  config.py        the settings and config.load
  probes.py        one probe per service
  semantic/        token.py: the signed token Cube expects (the client is planned, unit 5)
  commands/        smoke.py
  domain/          planned, unit 2
  seed/            planned, unit 2
  rdf/             planned, unit 3
  graph/           planned, unit 4
  agent/           planned, unit 6
  evals/           planned, unit 7
tests/             mirrors src/, plus guards/ (repository checks), support/ and stack.env
cube/model/cubes/  healthcheck.yml, the one cube that lets the smoke probe see Cube answer
compose.yaml       postgres, neo4j, cube
ontology/          planned, unit 3
questions/         planned, unit 2
```

The `graph/` directory under `tests/` holds the Neo4j read-only check, which tests the
driver and the container until `src/semantic_lab/graph/` exists.

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
- Do not read or print `.env`.
- Commit on a branch, one plain sentence as the message. Do not use `--no-verify`.
