# Unit 1, the skeleton: implementation plan

> For agentic workers: REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

Goal: a repository where `docker compose up -d` starts Postgres, Neo4j and Cube, one command
says whether each service and the local model answer, and the offline checks, the hook and CI
are in place for every later unit.

Architecture: settings come from the environment through one module with no defaults. Four
probes, one per service, return a result and never raise. The `smoke` command prints them.
Tests marked `db` start the same compose file under another project name and other ports.

Tech stack: Python 3.13, uv, httpx, psycopg, the neo4j driver, pytest, ruff, mypy, Docker
Compose, GitHub Actions.

Spec: `docs/superpowers/specs/2026-11-16-semantic-lab-design.md`. This plan covers item 1 of
its "Order of work" and its section "To confirm in unit 1".

## Global constraints

- Python 3.13, managed with `uv`. Never `pip`.
- Runtime dependencies in this unit: `httpx`, `psycopg[binary]`, `neo4j`. `rdflib`, `pyshacl`
  and `pyyaml` arrive with the units that use them.
- Dev dependencies: `pytest`, `pytest-xdist`, `ruff==0.14.0`, `mypy==1.18.2`.
- Images, pinned: `postgres:17.12`, `neo4j:2026.10.2-community`, `cubejs/cube:v1.8.26`.
- Every address, port and credential comes from the environment. No default lives in code.
- Development ports, bound to 127.0.0.1: Postgres 5440, Neo4j 7474 and 7687, Cube 4000. The
  test stack uses 5441, 7475, 7688 and 4001.
- Neo4j runs with a 1 GB heap and a 512 MB page cache, no plugins, and file import off.
- Pytest markers: `db` needs Docker, `model` calls Ollama. `addopts` deselects `model`. CI
  never runs `model`. `db` tests run without `-n`.
- `ruff check` and `mypy` pass. No formatter. A `noqa` or `type: ignore` names its code and
  says why.
- GitHub Actions are pinned to a commit with a `# vX.Y.Z` comment.
- Names are English. Prose follows the humanizer rules. Commits carry no attribution line and
  are authored as `AndresRubio <2109109+AndresRubio@users.noreply.github.com>`.
- All work happens on the branch `unit-1-skeleton` and ends in a pull request. Nobody merges
  it but the owner.

## Review focus

Each line names a condition the design implies and the task that tests it.

1. A setting is missing from the environment. The command names the variable on stderr and
   exits 2, with no traceback. Tasks 1 and 3.
2. One service is down. Its probe reports the failure within its timeout, the other probes
   still run, and the command exits 1. Tasks 2 and 3.
3. The test stack and the development stack run at once, next to boe-agent's containers on
   5433 and 5434. Their ports and project names never overlap. Task 1.
4. Ollama answers and the model named in the settings is not pulled. The probe fails and
   names the model. Task 2.
5. Cube answers its readiness check and then refuses the metadata request, or returns a body
   without `cubes`. The probe fails and says which. Task 2.

A probe's detail never contains a password or a secret. Task 2 tests that too.

## File map

```
pyproject.toml · .python-version · uv.lock
.env.example                      development values, safe to commit
compose.yaml                      postgres · neo4j · cube
cube/model/cubes/healthcheck.yml  one cube over `select 1`, the probe's target
scripts/check.sh · .githooks/pre-commit
.github/workflows/checks.yml · .github/dependabot.yml
src/semantic_lab/
  config.py                       Settings and load(env)
  probes.py                       Check and one function per service
  semantic/token.py               the signed token Cube's API expects
  commands/smoke.py               prints the probes
tests/
  stack.env                       the test stack's values
  conftest.py                     the `stack` fixture
  support/envfile.py              reads KEY=VALUE files
  test_config.py · test_probes.py
  semantic/test_token.py · semantic/test_cube_meta_db.py
  commands/test_smoke.py · commands/test_smoke_db.py
  graph/test_read_only_db.py
  agent/test_tool_call_model.py
  guards/test_env_files.py · guards/test_workflows.py
AGENTS.md · CLAUDE.md · CODING_STANDARDS.md
docs/superpowers/specs/measured-facts.md
```

## Task 1: project, settings and the offline check

Files:
- Create: `pyproject.toml`, `.python-version`, `src/semantic_lab/__init__.py`,
  `src/semantic_lab/config.py`, `.env.example`, `tests/__init__.py`, `tests/stack.env`,
  `tests/support/__init__.py`, `tests/support/envfile.py`, `tests/test_config.py`,
  `tests/guards/__init__.py`, `tests/guards/test_env_files.py`, `scripts/check.sh`,
  `.githooks/pre-commit`

Interfaces:
- Produces: `config.MissingSetting(Exception)` with attribute `name: str`;
  `config.Settings`, a frozen dataclass with `postgres_dsn`, `neo4j_uri`, `neo4j_user`,
  `neo4j_password`, `cube_url`, `cube_secret`, `ollama_url`, `model`, all `str`;
  `config.load(env: Mapping[str, str]) -> Settings`;
  `tests.support.envfile.read(path: Path) -> dict[str, str]`.

The sixteen keys of `.env.example`, with their development values:

```
SEMANTIC_LAB_POSTGRES_PORT=5440
SEMANTIC_LAB_POSTGRES_USER=lab
SEMANTIC_LAB_POSTGRES_PASSWORD=lab-local-postgres
SEMANTIC_LAB_POSTGRES_DB=lab
SEMANTIC_LAB_POSTGRES_DSN=postgresql://lab:lab-local-postgres@127.0.0.1:5440/lab
SEMANTIC_LAB_NEO4J_HTTP_PORT=7474
SEMANTIC_LAB_NEO4J_BOLT_PORT=7687
SEMANTIC_LAB_NEO4J_URI=bolt://127.0.0.1:7687
SEMANTIC_LAB_NEO4J_USER=neo4j
SEMANTIC_LAB_NEO4J_PASSWORD=lab-local-graph
SEMANTIC_LAB_CUBE_PORT=4000
SEMANTIC_LAB_CUBE_URL=http://127.0.0.1:4000
SEMANTIC_LAB_CUBE_SECRET=lab-local-cube-secret
SEMANTIC_LAB_CUBE_DEV_MODE=true
SEMANTIC_LAB_OLLAMA_URL=http://127.0.0.1:11434
SEMANTIC_LAB_MODEL=qwen2.5-coder:7b
```

`tests/stack.env` has the same keys with ports 5441, 7475, 7688 and 4001, passwords ending
`-test`, and `SEMANTIC_LAB_CUBE_DEV_MODE=false`.

- [ ] Step 1: create the branch `unit-1-skeleton`, write `pyproject.toml` (package
  `semantic-lab`, `requires-python = ">=3.13"`, hatchling, `src/semantic_lab`, the
  dependencies and markers from Global constraints, `addopts = "-m 'not model'"`, ruff
  `select = ["E4", "E7", "E9", "F", "W", "B", "RUF100"]` with `target-version = "py313"`, mypy
  over `src` and `tests` with `warn_unused_ignores` and `warn_redundant_casts`) and
  `.python-version` (`3.13`). Run `uv sync --extra dev`. Expected: a `uv.lock` and exit 0.
- [ ] Step 2: write the failing tests in `tests/test_config.py`:

```python
def test_load_reads_the_eight_settings():
    settings = config.load(envfile.read(ROOT / ".env.example"))
    assert settings.postgres_dsn == "postgresql://lab:lab-local-postgres@127.0.0.1:5440/lab"
    assert settings.model == "qwen2.5-coder:7b"

@pytest.mark.parametrize("name", ["SEMANTIC_LAB_POSTGRES_DSN", "SEMANTIC_LAB_NEO4J_URI",
    "SEMANTIC_LAB_NEO4J_USER", "SEMANTIC_LAB_NEO4J_PASSWORD", "SEMANTIC_LAB_CUBE_URL",
    "SEMANTIC_LAB_CUBE_SECRET", "SEMANTIC_LAB_OLLAMA_URL", "SEMANTIC_LAB_MODEL"])
def test_a_missing_or_empty_setting_is_named(name):
    env = envfile.read(ROOT / ".env.example")
    for broken in ({k: v for k, v in env.items() if k != name}, {**env, name: ""}):
        with pytest.raises(config.MissingSetting) as caught:
            config.load(broken)
        assert caught.value.name == name
```

- [ ] Step 3: write the failing tests in `tests/guards/test_env_files.py`:

```python
def test_both_files_have_the_same_keys(): ...           # set(example) == set(stack)
def test_each_dsn_and_address_matches_its_parts(): ...  # DSN, bolt URI and Cube URL rebuilt from user, password, db and ports, for both files
def test_no_port_is_shared(): ...                       # the 8 port values are distinct, and none is 5433 or 5434
def test_env_is_ignored_by_git(): ...                   # `git check-ignore .env` exits 0
```

- [ ] Step 4: run `uv run pytest tests/test_config.py tests/guards -q`. Expected: FAIL, the
  modules do not exist.
- [ ] Step 5: implement `tests/support/envfile.py` (`read` skips blank lines and lines
  starting with `#`, splits on the first `=`) and `src/semantic_lab/config.py`, then write the
  two env files.
- [ ] Step 6: run the same command. Expected: PASS.
- [ ] Step 7: copy `scripts/check.sh` and `.githooks/pre-commit` from
  `~/Desktop/projects/boe-agent`. In `check.sh` replace `boe-agent-checked` with
  `semantic-lab-checked`, `boe-agent-check-index` with `semantic-lab-check-index`, the pytest
  marker expression with `"not db and not model"`, and rewrite the header comment for this
  repo's one workflow, `checks.yml`. Translate the hook's two Spanish lines to English. Run
  `git config core.hooksPath .githooks` and `scripts/check.sh`. Expected: `==> all checks
  passed`.
- [ ] Step 8: commit, with this plan file in the same commit: "Add the Python project, the
  settings module and the offline check".

## Task 2: the token and the four probes

Files:
- Create: `src/semantic_lab/semantic/__init__.py`, `src/semantic_lab/semantic/token.py`,
  `src/semantic_lab/probes.py`, `tests/semantic/__init__.py`, `tests/semantic/test_token.py`,
  `tests/test_probes.py`

Interfaces:
- Produces: `token.sign(secret: str, now: int, ttl: int = 300) -> str`, an HS256 JWT with
  payload `{"iat": now, "exp": now + ttl}`, built with `hmac`, `hashlib`, `base64` and `json`;
  `probes.Check`, a frozen dataclass with `service: str`, `ok: bool`, `detail: str`;
  `probes.postgres(dsn: str, timeout: float = 5.0) -> Check`;
  `probes.neo4j(uri: str, user: str, password: str, timeout: float = 5.0) -> Check`;
  `probes.cube(url: str, secret: str, client: httpx.Client, now: int) -> Check`;
  `probes.ollama(url: str, model: str, client: httpx.Client) -> Check`.

Behaviour the tests pin: a probe never raises. On failure `detail` is the exception's class
name and the first line of its message, or the reason listed below. `cube` calls
`GET {url}/readyz`, then `GET {url}/cubejs-api/v1/meta` with header
`Authorization: <token>`. `ollama` calls `GET {url}/api/tags`.

- [ ] Step 1: write the failing tests in `tests/semantic/test_token.py`:

```python
def test_token_has_three_parts_and_a_valid_signature(): ...  # recompute HMAC-SHA256 over "header.payload" with the secret
def test_payload_carries_iat_and_exp():                      # sign("s", now=1000, ttl=300) -> {"iat": 1000, "exp": 1300}
def test_header_is_hs256_jwt():                              # {"alg": "HS256", "typ": "JWT"}
```

- [ ] Step 2: write the failing tests in `tests/test_probes.py`, using
  `httpx.Client(transport=httpx.MockTransport(handler))` for Cube and Ollama:

```python
def test_postgres_on_a_closed_port_fails_without_the_password():
    check = probes.postgres("postgresql://lab:hunter2-secret@127.0.0.1:1/lab", timeout=2)
    assert (check.service, check.ok) == ("postgres", False)
    assert "hunter2-secret" not in check.detail

def test_neo4j_on_a_closed_port_fails_without_the_password(): ...  # bolt://127.0.0.1:1, same two assertions
def test_cube_ok_counts_the_cubes(): ...            # readyz 200, meta {"cubes": [{}, {}]} -> ok, detail "2 cubes"
def test_cube_sends_a_signed_token(): ...           # the meta request's Authorization equals token.sign(secret, now)
def test_cube_not_ready(): ...                      # readyz 500 -> not ok, detail "readyz: HTTP 500"
def test_cube_meta_refused(): ...                   # meta 403 -> not ok, detail "meta: HTTP 403"
def test_cube_meta_without_cubes(): ...             # meta 200 {"error": "x"} -> not ok, detail "meta: no cubes in the response"
def test_cube_unreachable_keeps_the_secret_out(): ...  # handler raises httpx.ConnectError; secret not in detail
def test_ollama_ok_names_the_model(): ...           # {"models": [{"name": "qwen2.5-coder:7b"}]} -> ok
def test_ollama_model_not_pulled(): ...             # {"models": [{"name": "other:1b"}]} -> not ok, detail "model not pulled: qwen2.5-coder:7b"
def test_ollama_unreachable(): ...                  # ConnectError -> not ok
```

- [ ] Step 3: run `uv run pytest tests/semantic tests/test_probes.py -q`. Expected: FAIL.
- [ ] Step 4: implement `token.py` and `probes.py`. `postgres` connects with
  `connect_timeout` and runs `select 1`. `neo4j` opens a driver with `connection_timeout` and
  `max_transaction_retry_time=0` and runs `RETURN 1`.
- [ ] Step 5: run the same command, then `scripts/check.sh`. Expected: PASS, all checks
  passed.
- [ ] Step 6: commit: "Add the Cube token and a probe for each service".

## Task 3: the smoke command

Files:
- Create: `src/semantic_lab/commands/__init__.py`, `src/semantic_lab/commands/smoke.py`,
  `tests/commands/__init__.py`, `tests/commands/test_smoke.py`

Interfaces:
- Consumes: `config.load`, `config.MissingSetting`, the four probes.
- Produces: `smoke.report(checks: Sequence[Check], out: TextIO) -> int`, which prints one
  line per check as `ok    <service>  <detail>` or `FAIL  <service>  <detail>` and returns 0
  when every check is ok and 1 otherwise;
  `smoke.main(argv: Sequence[str], env: Mapping[str, str], out: TextIO, err: TextIO) -> int`,
  which accepts `--no-model`, returns 2 after writing `missing setting: <NAME>` to `err`, and
  otherwise runs the probes and returns `report`'s value. The module ends with the only
  `if __name__ == "__main__"` block, calling `sys.exit(main(sys.argv[1:], os.environ, sys.stdout, sys.stderr))`.

- [ ] Step 1: write the failing tests in `tests/commands/test_smoke.py`:

```python
def test_report_prints_one_line_per_check_and_returns_0(): ...
def test_one_failed_check_returns_1_and_the_others_still_print(): ...
def test_a_missing_setting_exits_2_and_names_it():
    env = {k: v for k, v in envfile.read(ROOT / ".env.example").items() if k != "SEMANTIC_LAB_CUBE_URL"}
    assert smoke.main([], env, out, err) == 2
    assert err.getvalue() == "missing setting: SEMANTIC_LAB_CUBE_URL\n"
    assert out.getvalue() == ""
def test_everything_down_exits_1_with_four_fail_lines(): ...   # every address on 127.0.0.1:1
def test_no_model_leaves_ollama_out(): ...                     # three lines, none for ollama
```

- [ ] Step 2: run `uv run pytest tests/commands -q`. Expected: FAIL.
- [ ] Step 3: implement `smoke.py`. `main` builds one `httpx.Client(timeout=5.0)` for the two
  HTTP probes and takes `now` from `time.time()`.
- [ ] Step 4: run the same command, then `scripts/check.sh`. Expected: PASS.
- [ ] Step 5: commit: "Add the smoke command".

## Task 4: the compose stack and the tests that need it

Files:
- Create: `compose.yaml`, `cube/model/cubes/healthcheck.yml`, `tests/conftest.py`,
  `tests/commands/test_smoke_db.py`, `tests/semantic/test_cube_meta_db.py`,
  `tests/graph/__init__.py`, `tests/graph/test_read_only_db.py`

Interfaces:
- Consumes: `config.load`, the probes, `token.sign`, `envfile.read`.
- Produces: the session fixture `stack() -> Settings` in `tests/conftest.py`.

What the compose file fixes:
- `postgres`: image `postgres:17.12`, `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`
  from the `SEMANTIC_LAB_POSTGRES_*` variables, port
  `127.0.0.1:${SEMANTIC_LAB_POSTGRES_PORT}:5432`, a `pg_isready` healthcheck, a named volume.
- `neo4j`: image `neo4j:2026.10.2-community`, `NEO4J_AUTH` built from the user and password,
  heap initial and max `1G`, page cache `512M`,
  `NEO4J_dbms_security_allow__csv__import__from__file__urls=false`, no `NEO4J_PLUGINS`, ports
  `127.0.0.1:${SEMANTIC_LAB_NEO4J_HTTP_PORT}:7474` and
  `127.0.0.1:${SEMANTIC_LAB_NEO4J_BOLT_PORT}:7687`, a named volume.
- `cube`: image `cubejs/cube:v1.8.26`, `CUBEJS_DB_TYPE=postgres`, host `postgres`, port 5432,
  name, user and password from the same variables, `CUBEJS_API_SECRET` from
  `SEMANTIC_LAB_CUBE_SECRET`, `CUBEJS_DEV_MODE` from `SEMANTIC_LAB_CUBE_DEV_MODE`, port
  `127.0.0.1:${SEMANTIC_LAB_CUBE_PORT}:4000`, `./cube/model` mounted read-only at
  `/cube/conf/model`, and `depends_on` postgres healthy.
- Every variable uses the `${NAME:?}` form, so a missing one stops compose with its name.

`cube/model/cubes/healthcheck.yml`:

```yaml
cubes:
  - name: healthcheck
    sql: "select 1 as n"
    measures:
      - name: rows
        type: count
        meta:
          iri: "urn:semantic-lab:healthcheck"
```

The `stack` fixture reads `tests/stack.env`, runs
`docker compose -p semantic-lab-test --env-file tests/stack.env up -d`, then calls the three
service probes once a second until all are ok. After 180 seconds it fails with the last
details and the output of `docker compose -p semantic-lab-test logs --tail 50`. It yields
`config.load(...)` of that file and runs `down -v` at the end.

- [ ] Step 1: write the failing tests, each marked `db` and taking `stack`:

```python
# tests/commands/test_smoke_db.py
def test_smoke_passes_on_the_stack(stack): ...   # main(["--no-model"], env_of_stack_file, out, err) == 0, three "ok" lines

# tests/semantic/test_cube_meta_db.py
def test_meta_returns_each_members_meta(stack):
    # GET /cubejs-api/v1/meta with token.sign(stack.cube_secret, now)
    # the cube "healthcheck" has a measure "healthcheck.rows" whose "meta" == {"iri": "urn:semantic-lab:healthcheck"}
def test_a_token_signed_with_another_secret_is_refused(stack): ...   # status 401 or 403

# tests/graph/test_read_only_db.py
def test_a_write_in_a_read_transaction_fails(stack):
    # session.execute_read(lambda tx: tx.run("CREATE (:Probe)").consume()) raises neo4j.exceptions.ClientError
    # afterwards MATCH (n:Probe) RETURN count(n) is 0
```

- [ ] Step 2: run `uv run pytest -m db -q`. Expected: FAIL, there is no compose file.
- [ ] Step 3: write `compose.yaml`, the healthcheck cube and the fixture.
- [ ] Step 4: run `uv run pytest -m db -q`. Expected: PASS. If the metadata test or the
  read-transaction test fails because the service behaves differently from the design, stop
  and report: the design's sections "The agent" and "Architecture" depend on both.
- [ ] Step 5: copy `.env.example` to `.env`, run `docker compose up -d`, wait, then
  `uv run --env-file .env python -m semantic_lab.commands.smoke`. Expected: four `ok` lines
  and exit 0. Run `docker stats --no-stream` and note the memory of the three containers for
  Task 6. Then `docker compose down`.
- [ ] Step 6: run `scripts/check.sh`, then commit: "Add the compose stack, the healthcheck
  cube and the tests that run against them".

## Task 5: CI and the workflow guard

Files:
- Create: `.github/workflows/checks.yml`, `.github/dependabot.yml`,
  `tests/guards/test_workflows.py`

- [ ] Step 1: write the failing test in `tests/guards/test_workflows.py`:

```python
def test_every_action_is_pinned_to_a_commit_with_its_version():
    # every line matching `uses:` in .github/workflows/*.yml matches
    # r"uses: [\w./-]+@[0-9a-f]{40} # v\d+\.\d+\.\d+$"
def test_the_workflow_never_selects_the_model_marker(): ...   # no line of checks.yml contains "-m model"
```

- [ ] Step 2: run `uv run pytest tests/guards/test_workflows.py -q`. Expected: FAIL.
- [ ] Step 3: write `checks.yml`, named `checks`, on pushes to `main`, pull requests and
  `workflow_dispatch`, with `permissions: contents: read` and the concurrency group
  `checks-${{ github.ref }}`. Three jobs on `ubuntu-latest`, each starting with
  `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`,
  `astral-sh/setup-uv@68559e99cc807c1eb7e9238fd43a15bba460eec2 # v10.3.3` (with
  `version: latest-known`) and `uv sync --extra dev --locked`: `static` runs `uv run ruff
  check` and `uv run mypy`; `offline` runs `uv run pytest -n auto -m "not db and not model"`;
  `db` runs `uv run pytest -m db`. Write `dependabot.yml` for `github-actions`, weekly, one
  group for all actions.
- [ ] Step 4: run the test and `scripts/check.sh`. Expected: PASS.
- [ ] Step 5: commit: "Add the checks workflow and Dependabot for its actions".

## Task 6: the model check, the repository's instructions and the pull request

Files:
- Create: `tests/agent/__init__.py`, `tests/agent/test_tool_call_model.py`, `AGENTS.md`,
  `CLAUDE.md`, `CODING_STANDARDS.md`, `docs/superpowers/specs/measured-facts.md`
- Modify: `README.md` (the Status section)

- [ ] Step 1: write `tests/agent/test_tool_call_model.py`, marked `model`. It posts to
  `{SEMANTIC_LAB_OLLAMA_URL}/api/chat` (settings from `.env`, through `config.load`) with
  `stream: false`, `options: {"temperature": 0, "seed": 7}`, the user message "Revenue by
  origin country for 2025, by quarter." and one tool, `cube_query`, whose parameters are
  `measures` (array of strings), `dimensions` (array of strings), `filters` (array of objects
  with `member`, `operator` and `values`) and `time` (object with `dimension`, `granularity`
  and `date_range`). It asserts that `message.tool_calls` has one entry, its function name is
  `cube_query`, and its arguments are a dict whose `measures` is a non-empty list of strings.
- [ ] Step 2: run `uv run --env-file .env pytest -m model -q` with Ollama running. Record the
  outcome either way. A failure here is a finding for unit 6 and does not block this unit.
- [ ] Step 3: write `docs/superpowers/specs/measured-facts.md`, dated, with: the three image
  tags; Cube's licence as `gh api repos/cube-js/cube/license -q .license.spdx_id` reports it;
  that the metadata endpoint returns each member's `meta` (Task 4); that Neo4j Community
  refuses a write in a read transaction (Task 4); the container memory noted in Task 4; and
  the result of Step 2 with the model's name.
- [ ] Step 4: write `CODING_STANDARDS.md` with these rules and the reason for each: one
  package per layer, and the imports the design's Architecture section allows; settings come
  only from `config.load`, and no module reads `os.environ` except a command's `__main__`
  block; a probe or tool never puts a credential in a message; tests mirror `src/`, a test
  that needs Docker is marked `db` and ends in `_db.py`, one that needs Ollama is marked
  `model` and ends in `_model.py`; a suppression names its code and says why; no ORM, no CLI
  framework, no async, no config system; a new runtime dependency needs the owner's yes.
- [ ] Step 5: write `AGENTS.md` (what the repo is, the commands with `[writes]` or
  `[read-only]` tags, the architecture tree, the test ladder: mirror file, package,
  `scripts/check.sh`, then `uv run pytest -n auto -m "not db and not model"` and
  `uv run pytest -m db` before a pull request; that the test stack and the development stack
  together need about twice the memory; where the design and the measured facts live) and a
  `CLAUDE.md` whose body is `@AGENTS.md`. Update the README's Status section to say the stack
  starts and which units remain.
- [ ] Step 6: run `scripts/check.sh --force`, `uv run pytest -n auto -m "not db and not
  model"` and `uv run pytest -m db`. Expected: all pass. Commit: "Add the model check, the
  measured facts and the repository's instructions".
- [ ] Step 7: a fresh agent reviews the branch against `CODING_STANDARDS.md` and the design.
  Fix what it finds, rerun Step 6.
- [ ] Step 8: push `unit-1-skeleton` and open a pull request against `main`. Check that the
  three CI jobs pass. The owner merges.
