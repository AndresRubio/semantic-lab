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

The content is a call with a sensible shape, but it is not the structured call the agent loop
expects. The invented member names (`revenue`, `origin_country`) are also not Cube members,
which is expected before any tool description names them. Unit 6 has to decide whether to
parse tool calls out of `content`, to try `gemma4`, or to change the tool description. The
test stays as written until then.
