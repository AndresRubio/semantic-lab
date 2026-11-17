# Measured facts

Measured on 2026-11-16, on the owner's Mac (M1 Pro, 16 GB, Docker with 7.748 GiB assigned).
The design lists these as "to confirm in unit 1". Each entry says what was run.

## Images

These pulled and ran: `postgres:17.12`, `neo4j:2026.10.2-community` and `cubejs/cube:v1.8.26`.

## Cube's licence

`gh api repos/cube-js/cube/license -q .license.spdx_id` prints `NOASSERTION`, where the design
expected Apache 2.0. The licence file says the repository is covered by one of two licences,
Apache 2.0 or MIT, and that Apache 2.0 is the default unless a file header or a package
`LICENSE` names another. GitHub cannot reduce that to one identifier, which is why it reports
none.

## Cube's metadata endpoint

The endpoint returns each member's `meta`. `tests/semantic/test_cube_meta_db.py` passes
against `cubejs/cube:v1.8.26`.

## Neo4j Community and writes

Neo4j Community refuses a write in a read transaction. `tests/graph/test_read_only_db.py`
passes against `neo4j:2026.10.2-community`: the driver raises `ClientError` and no node is
created.

## Cube Store

The design did not expect this one. With `CUBEJS_DEV_MODE=false`, Cube failed `/readyz` and
asked for Cube Store. The Cube documentation gives `cubestore` as the production default of
`CUBEJS_CACHE_AND_QUEUE_DRIVER`. `compose.yaml` sets it to `memory`, so the stack stays at three
containers. Unit 5 should look at this again when real queries run.

## Memory

Read with `docker stats --no-stream` about ten seconds after `docker compose up -d`, with the
development values and no data loaded:

| Container | Memory |
|---|---|
| Cube | 415.6 MiB on the first reading, 308.6 MiB on a second |
| Neo4j | 1.29 GiB |
| Postgres | 48 MiB |

The total is about 1.7 GiB, under the design's estimate of near 3 GB. It will grow once data
is loaded.

## Smoke command

Against that stack the smoke command printed four `ok` lines: postgres, neo4j, cube (with one
cube) and ollama (with the model present).

## Tool calls from the local model

`tests/agent/test_tool_call_model.py` asks `qwen2.5-coder:7b` through `/api/chat` (Ollama
0.40.16, temperature 0, seed 7) for "Revenue by origin country for 2025, by quarter." with the
`cube_query` tool. It failed on all three runs with the same reply. The model put its call in
`message.content` as JSON text and left `message.tool_calls` empty:

```json
{"role": "assistant", "content": "{\"name\": \"cube_query\", \"arguments\": {\"dimensions\": [\"origin_country\"], \"measures\": [\"revenue\"], \"time\": {\"dimension\": \"quarter\", \"granularity\": \"quarter\", \"date_range\": [\"2025\"]}}}"}
```

The agent loop reads only `tool_calls`, so this reply counts as no call. The member names it
chose (`revenue`, `origin_country`) are its own guesses, since the test's tool description names
no members. Unit 6 has to decide whether to
parse tool calls out of `content`, to try `gemma4`, or to change the tool description. The
test stays as written until then.

## The seed (unit 2)

Measured on 2026-11-16 on the same Mac, on the test stack (`semantic-lab-test`, ports 5441,
7475, 7688 and 4001), never the development stack. The stack was started with
`docker compose -p semantic-lab-test -f compose.yaml --env-file tests/stack.env up -d`. The
smoke command printed three `ok` lines on its first run, and the seed ran once against the
fresh Postgres. The numbers below were measured again on 2026-11-17, after the roast batches
were made to follow demand and the farm names made unique.

- Seed time: `time uv run --env-file tests/stack.env python -m semantic_lab.commands.seed`
  took 8.47 s of wall time on the first run and 7.79 s on a second (1.09 s and 1.00 s of user
  time). It generates the dataset, drops and creates the 17 tables and copies the rows in one
  transaction. The Mac's load average was above 27 from other containers during both runs, so
  the wall time includes waiting for a CPU. The earlier reading of 1.98 s (0.66 s of user time)
  came from a quiet machine, and the dataset is no larger now.
- Database size: `select pg_size_pretty(pg_database_size(current_database()))`, run through
  `exec -T postgres psql` after the seed, printed `19 MB`.
- Postgres memory: `docker stats --no-stream` right after the seed showed the Postgres
  container at 36.59 MiB, against 48 MiB in the table above with no data loaded. The two
  readings were taken on different stacks and moments, so they say only that loading the seed
  did not make Postgres grow past tens of megabytes. In the same reading Neo4j was at
  1.329 GiB and Cube at 163 MiB.

Row counts of the dataset for the default seed (20240101), read with `generate(taxonomy,
DEFAULT_SEED)` and equal to the seed command's output:

| Table | Rows |
|---|---|
| `cooperative` | 15 |
| `cooperative_certification` | 12 |
| `farm` | 120 |
| `shipment` | 80 |
| `lot` | 600 |
| `lot_farm` | 1,194 |
| `product` | 40 |
| `product_flavour` | 81 |
| `roast_batch` | 3,000 |
| `roast_batch_lot` | 4,527 |
| `customer` | 300 |
| `sales_order` | 20,000 |
| `order_line` | 60,000 |
| `quality_incident` | 2 |
| `concept` | 70 |
| `concept_alt_label` | 18 |
| `concept_closure` | 162 |

The pinned sha256 digest of the default seed's rows, `PINNED` in `tests/seed/test_generate.py`,
is `f7d93173cd5b845b501852178b013cd8cce9a45dd9ac8c35261f65808efd7180`. It is the same under
`PYTHONHASHSEED=0` and `PYTHONHASHSEED=1`.

Revenue for 2025 totals 9,613,814.74 euros whichever way it is cut. The three stored answers
`questions/expected/metric-revenue-by-country-2025.json` (six countries),
`hierarchy-revenue-by-continent-2025.json` (three continents) and
`metric-revenue-by-quarter-2025.json` (four quarters) each sum to that figure when added with
`Decimal`. The sums were checked by hand-run Python, not by the questions command.

Roast batches follow demand: a batch's output is what was sold from it plus an unsold remainder
of 2 to 20 percent of that, rounded up to the cent, and a batch nobody ordered from gets a drawn
output of 60 to 400 kg. Read from `generate(taxonomy, DEFAULT_SEED)`, no batch sells more than
its output, where the share was 876 of 3,000 before the change (0 of 3,000 now). The 26 batches
with no sales hold the drawn outputs. Across all 3,000 batches the largest `output_kg` is
1,978.80 kg and the median is 121.435 kg (the mean of the two middle values), and the smallest
is 0.29 kg, a batch whose only sale was one small bag.
