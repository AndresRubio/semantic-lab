# Coding standards

Each rule has its reason, so a case the rule does not cover can be decided from the reason.

## Layers

Each layer of the design's Architecture section is one package under `src/semantic_lab/`:
`domain`, `seed`, `rdf`, `graph`, `semantic`, `agent`, `evals` and `commands`. A package
holds one layer, so a change to one store or one tool has a known place.

The import directions that hold today, enforced by `tests/guards/test_layers.py`:

| Layer | May import from our code | Reason |
|---|---|---|
| `domain/` | nothing, and only the standard library from outside | It is the vocabulary every other layer shares, and a dependency in it would pull that dependency into all of them. |
| `rdf/` | `domain/` | It reads Turtle and the mapping into the domain's types, exports a `Dataset` as RDF and validates a graph with SHACL. It has no reason to know the generator or a store. |
| `seed/` | `domain/` | The generator modules build the domain's records and are pure, so they read no file, no store and no taxonomy loader, and receive a `Taxonomy` as an argument. `load.py` is the one module that does I/O: it reads `schema.sql` and writes Postgres with `psycopg`. `requirements.py` checks a taxonomy against the tables the generator keys by concept (weights, ports, categories) before `generate` draws anything, so a taxonomy that does not fit fails with one `GenerationError` where it would otherwise raise a `KeyError` deep in a draw. |
| `evals/` | `domain/` | It reads the question files and runs a reference query on a connection it is given. Today it imports nothing from `domain/`, and the rule keeps it from learning how the seed or a loader produced the rows. |
| `semantic/` | nothing of ours | The Cube client is a boundary to one service and holds no domain knowledge. |
| `commands/` | any layer | A command is an entry point that wires layers together. |

Nothing imports `commands/`, because the layers must not depend on an entry point. The same holds
for the top-level modules, and `tests/guards/test_layers.py` checks both. A second guard in that
file keeps the generator pure: inside `seed/`, only `load.py` may import a third-party module, and
every other module imports only the standard library, `semantic_lab.domain` and `semantic_lab.seed`. `graph/` and
`agent/` have no line yet: the unit that adds each one settles which packages it imports,
writes that down here and adds it to the test.

Four modules sit at the top level beside the layer packages: `config.py`, `pg.py`, `probes.py`
and `redaction.py`. `commands/` and the tests import them. The layer packages do not import
`pg` or `probes`, and `tests/guards/test_layers.py` checks it. `pg.py` opens every Postgres
connection, with a connect timeout and an error line that holds no credential, so a command
and a probe fail the same way. `probes.cube` asks Cube's metadata endpoint itself today. Unit 5
adds the Cube client to `semantic/` and decides whether the probe goes through that client.
`redaction.py` turns an exception into one line that holds no credential, and `pg.py`,
`probes.py` and the commands share it.

The design settles no other direction. The unit that adds a package settles which packages it
imports, writes that down here and adds a test for it.

## Settings

Modules under `src/` take settings only from `config.load`, and they receive the result as an
argument. `os.environ` is read in one place: the `if __name__ == "__main__"` block of a
command, which passes it to `config.load`. A settings value has no default in code, because a
default hides a missing setting until it breaks something far from the cause, and because the
same code has to run on the Mac and on AWS.

Two test cases differ. A test marked `model` passes `os.environ` to `config.load`, because it
runs against whatever the developer has started. A `db` test reads `tests/stack.env`, so it
never depends on the developer's `.env`. The `stack` fixture reads `os.environ` only to remove
the `SEMANTIC_LAB_*` keys before it runs Docker Compose, because Compose lets the shell's
variables win over `tests/stack.env`.

## Credentials

A probe or tool never puts a credential in a message, a result or an exception text. Those
strings end up in logs, traces and the model's context.

## Tests

- Tests mirror `src/`: the test for `src/semantic_lab/x/y.py` is `tests/x/test_y.py`. A reader
  finds a test from the code and the code from the test. A test for a planned layer sits in
  that layer's future directory, as `tests/graph/` and `tests/agent/` do today.
- A module that holds only constants or type definitions (`seed/names.py`, `seed/planted.py`,
  `domain/errors.py`) needs no mirror test file, because the tests of the
  modules that use them cover them.
- A test that needs Docker is marked `db` and its file ends in `_db.py`.
- A test that needs Ollama is marked `model` and its file ends in `_model.py`.
- The marker and the suffix together let a person or a script pick the expensive tests by name.
  `addopts` deselects `model`, and CI never runs it, because its runners have no Ollama.
- `db` tests run without `-n`, because they share one stack.

## Suppressions

A `noqa` or `type: ignore` names its code and says why. A bare one hides whatever the tool
reports next on that line, and `RUF100` and `warn_unused_ignores` flag the ones that
stopped being needed.

## Dependencies and style

- No ORM, no CLI framework, no async and no config system. The lab teaches what these
  would hide, and the code stays short enough to show in an interview.
- A new runtime dependency needs the owner's yes. The runtime dependencies today are `httpx`,
  `psycopg[binary]`, `neo4j`, `rdflib`, `pyshacl` and `pyyaml`. Each one is a cost the owner pays on every upgrade.
- Names are English, because the repository will be shown to interviewers.
- `ruff check` and `mypy` pass. There is no formatter.
