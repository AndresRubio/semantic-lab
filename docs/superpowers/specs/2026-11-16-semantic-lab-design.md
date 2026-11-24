# semantic-lab: design

The owner approved this design on 2026-11-16, along with the name, a public repository under
the MIT licence, and the invented domain.

## What this is for

Andrés wants one repository where he can learn four things by building them against the same
data: a taxonomy, an ontology, a knowledge graph and a semantic layer. An agent sits on top and
answers questions in plain language. Which tools the agent holds is a setting, so the same
question can be asked with Cube, without Cube, with the graph, or with everything. The stack
runs on his Mac with Docker and Ollama. A later step puts it on AWS so he can show it in
interviews.

The repo is a success when he can open it in an interview and show, with numbers, where a
semantic layer helps a small local model answer correctly, where a graph helps, and where
neither does.

## Four terms as this repo uses them

A taxonomy is a controlled list of concepts arranged from broad to narrow, with synonyms. Its
standard is SKOS. Here it answers "what does the user mean by fruity?" and "which concepts sit
under it?".

An ontology says which kinds of things exist, which relations may hold between them and which
constraints apply. Its standards are RDFS and OWL for the classes and properties, and SHACL for
the constraints. Here it is the one written definition of what a lot, a roast batch or an order
line is.

A knowledge graph is the data itself stored as things and relations, typed by the ontology.
Here it lives in Neo4j, which is a property graph and stores no RDF. The loader that turns the
ontology's terms into Neo4j labels and relationship types is part of what the repo teaches.

A semantic layer defines measures, dimensions and joins once, over SQL tables, and compiles a
request such as "revenue by country and month" into SQL. Here that is Cube Core.

Cube does not translate ontologies into SQL. It translates its own model of cubes, views,
measures and dimensions into SQL, and it knows nothing about RDF or OWL. This repo connects
the two by hand: every Cube measure and dimension carries the IRI of the ontology term it
measures, in its `meta` field, and a test fails when a member has no term or a term marked as
measurable has no member.

## Goals

- One invented domain, small enough to hold in your head, with questions of four kinds: a
  metric over time, a path through relations, a rollup over a concept hierarchy, and a mix.
- Each of the four layers is written by hand in its standard form and checked by a test.
- An agent whose tool set is a named profile, with a command to ask one question under one
  profile and one model.
- An evaluation that runs a fixed question set under every profile and model and scores the
  answers against known results, with no judge model.
- `docker compose up` plus one seed command gives a working stack on a 16 GB Mac.
- Nothing in the code assumes the Mac, so the same compose file can run on one AWS machine.

## Non-goals

- OWL reasoning beyond subclass and subproperty. No description-logic reasoner.
- Building the graph from documents with a model. The data is generated, so every answer is
  known.
- Vector search and GraphRAG over text. It can be a later unit once the four layers work.
- Cube's commercial features: its hosted agent, Analytics Chat and its official MCP server.
- A web interface and the AWS deployment. Each gets its own design later.

What would make it a failure even if it runs: four separate demos that share nothing, or a
chat that looks good and has no measured result behind it.

## What is on the machine

Measured on 2026-11-16. The Mac is an M1 Pro with 16 GB. Docker 29.9.1 has 10 CPUs and 8.3 GB
assigned, and two boe-agent Postgres containers already run on 5433 and 5434. Ollama is
0.40.16. `ollama show` lists the `tools` capability for `gemma4:latest` (8.0B, 9.6 GB),
`qwen2.5-coder:7b` (4.7 GB) and `qwen2.5-coder:3b` (1.9 GB). `nimble:9b-q4_K_M` does not list
it. `gh` is logged in as AndresRubio.

`gemma4` at 9.6 GB plus the containers is tight on 16 GB, so the default model for
development is `qwen2.5-coder:7b`, and `gemma4` runs for evaluation with the boe-agent
containers stopped. The compose file caps Neo4j at a 1 GB heap and a 512 MB page cache, which
is plenty for a graph under 100,000 nodes, so the three containers stay near 3 GB.

## The domain

Cumbre Coffee is an invented importer and roaster. It buys green coffee lots from
cooperatives, ships them, roasts them in batches and sells bags to cafés and shops. Every
customer is an organisation, so the data holds no people.

The things: country, region, cooperative, farm, lot, shipment, roast batch, product, customer,
order, order line and quality incident. A cooperative points at its region, and a farm belongs
to a cooperative, so a farm has no region of its own. A lot belongs to one cooperative, is
harvested from one or more of that cooperative's farms, and has a processing method, a variety
and a harvest date. Farm names are unique. Certifications are a table of dated periods per cooperative, so a
certification can lapse. A shipment carries lots. A roast batch consumes one lot, or several
when the product is a blend. A product is made from roast batches and has a category and
flavour notes. A one-lot product (single-origin, microlot or decaf) has an origin region and
is roasted only from the lots of that region. A blend has no origin region. A blend batch
splits its revenue among its lots by a `share` that sums to 1. Cumbre roasts to demand: a
batch has a planned size, and it is roasted larger when the orders from it need more, so no
batch sells more than it produced. An order line sells a quantity of a product from one roast batch to a customer. A quality incident recalls a lot.

In the ontology, regions are concepts of the geography taxonomy and have no class of their own.
`BatchComponent` is a class because RDF has no properties on a relation, and a blend batch's
`share` belongs to the pair of a batch and a lot.

The domain was picked because tracing a recalled lot forward to the customers who received it
is a path question that SQL handles badly and a graph handles in one pattern, while "revenue by
origin country per quarter" is the opposite.

Four taxonomies, each a SKOS concept scheme with labels in English and Spanish: geography
(continent, country, region), processing method (washed, natural with anaerobic under it,
honey with its grades), flavour (fruity, with berry and citrus under it, and so on) and product
category. Spanish synonyms such as "lavado" for washed give the agent something real to
resolve.

Target size for the seed: 6 countries, 24 regions, 15 cooperatives, 120 farms, 600 lots, 80
shipments, 3,000 roast batches, 40 products, 300 customers, 20,000 orders and 60,000 order
lines, dated 2024-01 to 2025-12. The generator is seeded, so two runs give the same rows. It
plants a few facts on purpose so that questions have answers worth checking: two recalled
lots, two blends that share farms, and a cooperative whose organic certification lapses in
mid 2025. The graph stays under 100,000 nodes.

The Turtle files are the source of the taxonomies, and Postgres holds a copy. The seed command
loads every concept into a `concept` table with a short key, and every ancestor and descendant
pair into a `concept_closure` table. Cooperatives (through their region), lots (through their
process) and products (through their category, origin region and flavour notes) point at concept
keys. This lets Cube filter on a concept key, and it gives the `sql` profile the same hierarchy
the other profiles get, so the comparison is fair.

## Questions the system must answer

The question set is the specification of behaviour. It reaches about 30 questions by the end
of unit 5, because each unit adds the questions its layer can answer. Each question is tagged
with the kind of answer it needs and stored with a reference query written by hand and the
result that query gives on the seed.

Each question also declares the shape of its answer: the columns wanted, in order, and which
of them identify a row. The question's text names those columns. Answers use business keys
and names (a lot code, a customer name, a country), never IRIs or database ids.

The questions are written to be answerable, and nothing is arranged so that a profile fails.
The `sql` profile may answer a path question with a recursive query. The report shows what
each profile did.

| Kind | Example | Layer that should answer it |
|---|---|---|
| Metric | Revenue by origin country per quarter in 2025 | Cube |
| Metric | Average margin of washed against natural products | Cube |
| Path | Which customers received bags from lot L-0417? | Graph |
| Path | Which farms supply both the Alba blend and the Brisa blend? | Graph |
| Hierarchy | Kilograms sold of fruity coffees in 2025 | Taxonomy, then Cube |
| Mixed | Revenue at risk from the two recalled lots | Graph, then Cube |

## Approaches considered

Where the graph lives. Neo4j Community Edition in Docker is free, GPLv3, and is the graph
database an interviewer is most likely to know. Apache AGE would put the graph inside the
Postgres that Cube already reads, with one container fewer, and teaches less that carries
over. An RDF triple store such as Fuseki or Oxigraph would keep the ontology and the data in
one model with SPARQL, and loses the property graph and Cypher. Picked: Neo4j Community, as
the owner asked, with the RDF side handled in Python.

How RDF reaches Neo4j. The neosemantics plugin (n10s) imports OWL, RDFS and SKOS into Neo4j
and can validate SHACL there. It is a Neo4j Labs project, outside the supported product. The
other way is to parse the Turtle files with `rdflib`, validate with `pyshacl`, and write nodes
and relationships with the official driver under an explicit mapping. Picked: the Python
loader, because the mapping from RDF to a property graph then sits in code you wrote and can
test. n10s is a later experiment to compare against.

How the ontology and Cube stay in step. One way is to generate the Cube model from the
ontology and a mapping file. The other is to write the Cube model by hand and check it against
the ontology in a test. Picked: by hand with a test, so the Cube modelling is learned
directly. Generation can come later.

How the agent is built. A framework (LangGraph, PydanticAI) would give a tool loop and
tracing on day one. A plain loop over Ollama's `/api/chat` with `tools` is about a hundred
lines, has no dependency, and every step of it can be shown in an interview. Picked: the plain
loop, behind a small model interface so another provider can be added for AWS.

These four picks are Claude's calls, made because the owner handed over the how. The owner
chose Cube, Neo4j, Python, Ollama and Docker.

## Architecture

```
ontology/      taxonomy/*.ttl (SKOS) · ontology.ttl (RDFS/OWL) · shapes.ttl (SHACL) · mapping.yaml
cube/model/    cubes/*.yml · views/*.yml
questions/     the question set, each with its reference query and expected result
src/semantic_lab/
  domain/      the row types, the taxonomy, the ontology and the mapping as values, errors:
               standard library only
  seed/        the seeded generator and the Postgres schema
  rdf/         load Turtle, validate SHACL, read the mapping, export the rows as RDF
  graph/       project Postgres rows and taxonomy concepts into Neo4j; run read-only Cypher
  semantic/    the Cube client: read the model's metadata, run a query
  agent/       the model interface, the loop, the tools, the profiles
  evals/       the runner and the scorer
  commands/    the `python -m` entry points
compose.yaml   postgres · neo4j · cube
```

Postgres is the system of record. The generator writes it and nothing else does. Neo4j holds a
projection of the same rows plus the taxonomy concepts, rebuilt from Postgres and the Turtle
files by one command. Cube reads Postgres. The ontology folder is the written meaning, and
`mapping.yaml` has one entry per ontology class and property. An entry names the term's
Postgres table or column, its Neo4j label or relationship type, and its Cube members. Any of
the three may be `none`, written out, for a term that a store does not hold: a recall has no
Cube member, for example. A term may have several Cube members (a sum and an average of the
same amount), and each Cube member carries exactly one IRI in `meta.iri`.

Three checks hold the layers together:

1. The Turtle files parse, and the taxonomies and the ontology pass their own SHACL shapes.
   This runs offline.
2. Every class and property in the ontology has an entry in `mapping.yaml`. In unit 3 the
   check covers the ontology against the mapping, every column of the data tables being mapped
   once, and the Postgres targets, which exist as tables and columns of the generator's row
   types and, in the database suite, of the schema. A column also has to fit its property: it
   sits on a table of the property's domain, and its row type holds what the range needs.
   Units 4 and 5 add the Neo4j and Cube
   targets with their checks: the Cube members are checked offline against the model's YAML
   files and the Neo4j targets in the database suite, and every Cube member's `meta.iri` is an
   ontology term whose entry lists that member.
3. The first 200 orders of the generator's rows, taken in memory with the rows they name and
   exported as RDF through the mapping, pass the SHACL shapes. This runs offline, with no
   Postgres. The offline suite validates the first 200 orders, and `--full` validates every row
   in about two minutes.

## The agent

The model is asked to answer by calling tools and to finish by calling `final_answer` with
rows and a one-sentence explanation. The scorer reads those rows, so no judge model is needed.

| Tool | What it does |
|---|---|
| `taxonomy_search(text)` | Finds concepts by any label in either language and returns each with its scheme, IRI and narrower concepts |
| `cube_meta()` | Lists the views, measures and dimensions Cube exposes, with their descriptions |
| `cube_query(measures, dimensions, filters, time)` | Sends a structured query to Cube, which writes the SQL, and returns rows |
| `graph_schema()` | Lists the labels, relationship types and properties in Neo4j |
| `graph_query(cypher)` | Runs Cypher in a read transaction with a row limit and a timeout |
| `sql_schema()` and `sql_query(sql)` | The baseline without Cube: raw SQL through a read-only Postgres role with a statement timeout |
| `final_answer(rows, explanation)` | Ends the run |

Profiles are named sets of tools: `sql`, `cube`, `graph`, `cube+taxonomy`, `full` (taxonomy,
Cube and graph) and `full+sql`. One command asks one question:
`python -m semantic_lab.commands.ask --profile full --model qwen2.5-coder:7b "..."`, and it
prints each tool call as it happens.

The loop has a step limit. A tool error goes back to the model as the tool's result, so the
model can correct a query. Every run writes a trace as JSON lines: the question, the profile,
the model, each tool call with its arguments, its duration and the size of its result, and the
final answer.

`cube_query` takes a structured query and the client sends it to Cube's JSON endpoint. Cube
said in May 2026 that its SQL API is the main Core API from now on and that the JSON one stays
without new features, so the client lives in one module and can move to the SQL API without
touching the tool's contract.

A mixed question passes a result from one tool to the next through the model's context: the
graph returns lot or product keys and the model puts them in a Cube filter. There is no
composed tool in the first version. Every tool cuts its result at 200 rows and says so when it
does, and the planted recalls are sized so the list a mixed question carries stays well under
that. If small models still fail to carry the keys across, the report says so.

`taxonomy_search` returns concept keys together with the keys of everything narrower, so a
hierarchy question becomes one Cube filter on a list of keys.

The read-only Postgres role behind `sql_query` has to survive a rebuild. The seed command drops
and recreates all 17 tables, and a table's grants go with it, so the role needs
`pg_read_all_data`, or a grant written inside `schema.sql` so that every rebuild repeats it, to
keep its access afterwards.

Neo4j Community has no roles, so there is no read-only database user. `graph_query` has three
defences. It runs in a read transaction, which refuses writes, and a test proves that a
`CREATE` sent through the tool fails. It refuses any query containing `CALL` or `LOAD CSV`
before sending it, since a read transaction does not stop those. And the Neo4j container
installs no extra procedures and has file import switched off. The graph is also a projection
that one command rebuilds.

## Evaluation

`python -m semantic_lab.commands.evaluate` runs every question under every profile for each
model named, and writes one row per run: correct or not, the number of steps, the seconds
taken, and which tools were called.

`final_answer` takes rows as lists of values in the column order the question declared. The
scorer compares values by position and ignores column names. A result is correct when it has
the expected rows and no others, matched on the identifying columns, with numbers compared to
a stated tolerance, text compared without regard to case or surrounding spaces, and row order
ignored unless the question asks for one. An extra column makes the answer wrong.

Every run uses temperature 0 and a fixed seed, and each question runs three times per profile
and model, since a local model can still vary. The report gives counts, such as 7 of 10 path
questions, by profile, model and question kind. It sets no pass mark: with about 30 questions
the numbers describe what happened on this question set and support no wider claim. With 6
profiles, 2 models and 3 repetitions that is about 1,080 runs, so the runner can take a subset
of profiles, models or questions.

The questions are split in two files from the first day: a development set used while tuning
prompts and tool descriptions, and a held-out set that is run only to report.

## Tests

The offline suite needs no model and no Docker. It covers the Turtle files, the mapping
checks, the generator, the scorer, and the agent loop driven by a scripted model that replays
a list of tool calls. Tests marked `db` start Postgres, Neo4j and Cube and check the
projection, the reference queries and that each reference Cube query gives the same numbers as
its reference SQL. Tests marked `model` call Ollama and run only on the Mac. CI runs ruff,
mypy, the offline suite and the `db` suite, and on a pull request it also runs the ontology
command with `--full`. It never runs `model`, because GitHub's runners have no Ollama.

## Conventions

Python 3.13 with `uv`. Runtime dependencies: `httpx`, `psycopg`, `neo4j`, `rdflib`, `pyshacl`
and `pyyaml`. `ruff check` and `mypy` pass, `scripts/check.sh` runs every offline check so the
check-gate mod can use it, and CI pins its actions to commits. Names are English, since the
repo will be shown to interviewers. Prose follows the humanizer rules. The repo carries its
own `AGENTS.md`, a `CLAUDE.md` that imports it, and a `CODING_STANDARDS.md`.

Ports avoid boe-agent's: Postgres on 5440, Neo4j on 7474 and 7687, Cube on 4000.

## Order of work

1. Skeleton: the repo, `uv`, ruff, mypy, `scripts/check.sh`, CI, the compose file with three
   pinned images, `AGENTS.md`. It ends with a smoke test that each service answers.
2. Domain and seed: the Postgres schema, the generator, the planted facts, and the first
   questions with reference SQL. The four taxonomy files and `rdflib` arrive here too,
   earlier than first planned, because the seed needs the concept keys.
3. Ontology: the ontology, the SHACL shapes, the mapping file with its Postgres targets, the
   `ontology` command that runs the three checks and prints four lines (the first check has
   one line for the taxonomies and one for the ontology), and the checks themselves. The
   taxonomy files already exist from unit 2.
4. Knowledge graph: the projection into Neo4j, its constraints, the Neo4j targets in
   `mapping.yaml` with their check, and reference Cypher for the path questions.
5. Semantic layer: the Cube model and views, the Cube targets in `mapping.yaml`, the `meta.iri`
   check, and reference Cube queries that match the reference SQL.
6. Agent: the model interface, the loop, the tools, the profiles and the `ask` command.
7. Evaluation: the runner, the scorer, the two question files and the first report.
8. Comparison with NVIDIA Auto Ontology: point it at the seeded Postgres, let it draft its
   semantic layer with no hand edits, and score its answers on the same questions with the
   unit 7 scorer. It gets its own design first. Its README, read on 2026-11-18, says the
   default setup sends schema samples to NVIDIA's hosted models and needs four model roles
   (reasoning, non-reasoning, embedding and rerank). Nothing here has run it, so that design
   starts by measuring whether it runs on local models.

After that, each with its own design: a small web page for the demo, the AWS deployment, and
optional experiments (n10s, an MCP server over the same tools, vector search).

Unit 1 is built in a Claude Code session, because nothing can take an issue to a pull request
in a repo that does not exist. Once it is merged and `/issue-pipeline:setup` has run, units 2
to 7 can each be one or more GitHub issues for `/issue-pipeline:ship`.

## Later: ideas from AWS's Context Ontology Accelerator

AWS's Context Ontology Accelerator (COA,
[`aws/context-ontology-accelerator`](https://github.com/aws/context-ontology-accelerator), read
at release `v0.3.10` on 2026-11-19) does at production scale what this lab does by hand. It
reads a database's schema, induces an OWL ontology with R2RML mappings to SQL, stores named
metrics, and answers a question in tiers through an MCP server. Running it is not a candidate:
its getting-started guide prices a default deployment at "about $1,600/month" while idle, it
needs an AWS account, and its docs describe no local mode. Five of its ideas fit here. None is
built or designed. Each would get its own design, as an experiment after unit 7 unless its line
says otherwise.

1. The ontology as a query layer. COA's mappings let Ontop translate SPARQL over the ontology
   into SQL over the tables, so the data is never copied into a store. Here `mapping.yaml`
   already says which table and column each term comes from, and nothing queries the ontology:
   the `ontology` command only checks it. The experiment generates R2RML from `mapping.yaml`,
   runs Ontop beside Postgres, adds a `sparql_query` tool and an `ontology` profile, and gives
   the report a column for it. Ontop is a translator and holds no data, so this does not reopen
   the choice of Neo4j over a triple store. To confirm first: Ontop's image, its licence and
   its memory on this Mac. COA gives its Ontop task 1 vCPU and 2 GB by default.
2. A profile that calls no model. COA's first tier matches a question to a metric by name or
   synonym (an exact match, then a fuzzy string match at 0.88 or more), runs the metric's
   stored SQL as written, and declines when part of the question is left over. The same rule
   over Cube's measures gives the evaluation a baseline: how many questions a matcher answers
   before any model is asked.
3. Synonyms on measures. That first tier depends on each metric carrying synonyms. Here every
   ontology term has an English and a Spanish label, and `ontology.ttl` has no alternative
   labels. The change adds them to the measurable terms, copies them into each Cube member's
   `meta` beside `meta.iri`, returns them from `cube_meta()`, and extends the unit 5 check to
   them. It belongs in unit 5, and idea 2 needs it.
4. The spread across repetitions in the report. COA's context-manager README calls an A/B of
   one switch a null result because "every delta" sat "inside its cell's own seed spread".
   Unit 7 already runs each question three times. The report would print the spread beside
   each count and treat a difference inside it as no difference.
5. A mechanical ontology as a baseline for unit 8. COA's default induction makes one class per
   table, a datatype property per column and an object property per foreign key, before any
   model describes them. Deriving that from `schema.sql` with no model and comparing it with
   `ontology.ttl` shows what the hand modelling added (regions as concepts, `BatchComponent`,
   the two product subclasses) and gives unit 8 a second point of comparison.

Left out on purpose: COA's steward approval states, its roles and namespaces, its Bedrock
guardrails and its document pipeline, since GraphRAG is a non-goal here. Its MCP server has six
tools (`list_metrics`, `describe_schema`, `query`, `translate_sparql`, `rag_retrieval`,
`graph_traversal`), which changes nothing in the MCP experiment listed under "Order of work".
One caution for the AWS step comes from its docs: its guardrail rewrites a name in a question
to `{NAME}` before the model sees it, and its README measures the wrong answers that causes. A
guardrail here should leave a question's literals alone.

## Later: AWS

Nothing is designed here. Three constraints apply from the first unit so the later step stays
small: every address, port and credential comes from the environment; the model sits behind
the interface in `agent/`; and the whole stack runs from one compose file. The expected shape
follows boe-agent: one EC2 machine with the compose stack and Ollama, Pulumi in Python, and a
script that starts and stops it around an interview. Neo4j Community runs there in its
container. Aura Free is the alternative for the graph: its limit is 200,000 nodes and 400,000
relationships, and it pauses after three days without use.

## To confirm in unit 1

These come from memory or from secondary sources and get checked against the running
services before anything is built on them:

- The Cube image and tag to pin, and its licence file. Cube's own article says Core is Apache
  2.0; a third-party listing put it at v1.8.18 on 2026-11-03.
- That Cube's metadata endpoint returns each member's `meta`.
- The Neo4j Community image and tag to pin, and that a write inside a read transaction fails.
- That `qwen2.5-coder:7b` returns well-formed tool calls through `/api/chat` for a tool with
  nested arguments such as `cube_query`.

## Left to the builder

The exact Postgres columns, the Cypher constraints, whether order lines are nodes or
relationships (inside the 100,000-node limit), the prompt text, the trace field names, the
tolerance for numeric comparison, and how the `db` tests start their containers.
