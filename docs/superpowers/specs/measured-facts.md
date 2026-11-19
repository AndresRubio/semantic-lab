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
  took 2.24 s of wall time (0.70 s of user time). It generates the dataset, drops and creates
  the 17 tables and copies the rows in one transaction. The Mac was still under load from other
  projects' containers (load average about 10), so the wall time includes some waiting for a CPU.
  An earlier run the same day, at a load average above 27, took 7.79 s.
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
is `79bcee403c3717d5f1c726363ffa73d3a76f74c3322a92397375816d3724a143`. It is the same under
`PYTHONHASHSEED=0` and `PYTHONHASHSEED=1`.

Revenue for 2025 totals 9,613,814.74 euros whichever way it is cut. The three stored answers
`questions/expected/metric-revenue-by-country-2025.json` (six countries),
`hierarchy-revenue-by-continent-2025.json` (three continents) and
`metric-revenue-by-quarter-2025.json` (four quarters) each sum to that figure when added with
`Decimal`. The sums were checked by hand-run Python, not by the questions command.

Roast batches follow demand. Every batch draws a planned size of 60 to 400 kg, and a batch that
sold needs its sales plus an unsold remainder of 2 to 20 percent of them, rounded up to the cent.
Its output is the larger of the two: a batch that sells little keeps its planned size, and one
that sells more than that was roasted larger. Read from `generate(taxonomy, DEFAULT_SEED)`, no
batch sells more than its output, where the share was 876 of 3,000 before the change (0 of 3,000
now), and none is under 60 kg. Across all 3,000 batches the smallest `output_kg` is 61.04 kg, the
median 281.745 kg (the mean of the two middle values) and the largest 1,881.00 kg. 26 batches
have no sales. Only `roast_batch` rows changed from the previous digest, so the twelve stored
answers are byte for byte the same.

## The ontology (unit 3)

Measured on 2026-11-18 on the owner's Mac. `uv.lock` pins `pyshacl` 0.40.2 and `pyyaml` 6.0.3.

`pyshacl` 0.40.2 ships a `py.typed` marker and PyYAML 6.0.3 does not, so `types-PyYAML` supplies
its stubs. With the ontology passed as `ont_graph` and `inference="none"`, a shape with
`sh:targetClass sl:Product` reported a node typed only `sl:SingleLotProduct`, and the call left
the data graph as it was. `sh:closed`, `sh:pattern`, `sh:lessThan` on two `xsd:date` values,
`sh:equals` on a sequence path, `sh:zeroOrMorePath`, `sh:inversePath`, `sh:node`,
`sh:targetSubjectsOf` and `sh:sparql` with `GROUP BY` and `HAVING` worked as the SHACL
specification says. A SPARQL `SUM` over `xsd:decimal` shares 0.33, 0.33 and 0.34 compared equal
to 1. A plain string literal satisfies `sh:datatype xsd:string`. `rdflib` writes a `Decimal` as
`xsd:decimal` with its scale kept, an `int` as `xsd:integer` and a `date` as `xsd:date`. A
malformed shape (`sh:minCount "many"`) raises `pyshacl.errors.ConstraintLoadError`, a subclass
of `pyshacl.errors.ReportableRuntimeError`, as do `ShapeLoadError` and `ValidationFailure`.

`yaml.safe_load` keeps the last of two equal keys and says nothing: with `sl:weightKg` written
twice in `mapping.yaml`, the command printed four `ok` lines, so the reader now uses a loader
that refuses the second one. `rdflib` builds a literal whose text does not fit its datatype,
such as `"SL28"^^xsd:integer`, and logs a Python traceback for each one: a mapping that put
`lot.variety` under `sl:altitudeMetres` printed 600 of them for the first 5 orders. The mapping
check now refuses that mapping before the export runs.

For the seeds 20240101, 1, 7 and 99, every rule the data shapes state held on the generated
rows, checked in plain Python: dates in order, shares summing to 1, one component for a one-lot
batch and two to four for a blend, lots from the product's region, no batch oversold, farms in
the lot's cooperative, the code formats and the positive amounts. The SHACL features `sh:xone`,
`sh:uniqueLang`, `sh:languageIn`, `sh:in` and `sh:or` were not probed in a failing case before
the fault tables of the shapes tests.

The command reports 442 triples for the four taxonomies and 360 for `ontology.ttl`. The mapping
holds 14 classes and 50 properties and names 63 distinct Postgres columns. The default seed's
whole dataset exports to 666,094 triples in 6.2 s, and with the 442 taxonomy triples the data
graph holds 666,536. The first 200 orders with the rows they name give a data graph of 17,767
triples.

`python -m semantic_lab.commands.ontology` took 4.43 s of wall time for all four checks on the
first 200 orders. With `--full` it took 116.28 s on the 666,536 triples and conformed. The test
that validates the first 200 orders took 2.94 s. The plan's estimate of 16 s for a full
validation came from a probe with five shapes (16.37 s on 664,730 triples) and does not hold for
the real shapes, which take about two minutes. `--full` is run by hand and never by a test.
