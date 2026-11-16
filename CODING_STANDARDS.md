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
| `rdf/` | `domain/` | It reads Turtle into the domain's types. It has no reason to know the generator or a store. |
| `seed/` | `domain/` | The generator builds the domain's records and is pure, so it must not read a file, a store or a taxonomy loader. It receives a `Taxonomy` as an argument. |
| `evals/` | `domain/` | Questions and reference queries are checked against the domain's types, not against how the seed or a loader produced them. |
| `semantic/` | nothing of ours | The Cube client is a boundary to one service and holds no domain knowledge. |
| `commands/` | any layer | A command is an entry point that wires layers together. |

Nothing imports `commands/`, because the layers must not depend on an entry point. `graph/` and
`agent/` have no line yet: the unit that adds each one settles which packages it imports,
writes that down here and adds it to the test.

Three modules sit at the top level beside the layer packages: `config.py`, `probes.py` and
`redaction.py`. `commands/` and the tests import them. The layer packages do not import
`probes`. `probes.cube` asks Cube's metadata endpoint itself today. Unit 5 adds the Cube
client to `semantic/` and decides whether the probe goes through that client. `redaction.py`
turns an exception into one line that holds no credential, and `probes.py` and the two
commands that open a Postgres connection share it.

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
  `psycopg[binary]`, `neo4j` and `rdflib`. Each one is a cost the owner pays on every upgrade.
- Names are English, because the repository will be shown to interviewers.
- `ruff check` and `mypy` pass. There is no formatter.
