# Unit 2, the domain and its seed: implementation plan

> For agentic workers: REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

Goal: one command fills Postgres with the invented Cumbre Coffee data, the same rows on every
run, and a first set of questions is stored with reference SQL and the answers that SQL gives.

Architecture: the four taxonomies are SKOS Turtle files, read with `rdflib` into a plain
`Taxonomy` value. A pure generator turns that value and a seed number into a `Dataset` of
rows. A loader rebuilds the lab's tables from the two in one transaction. Questions live in
TOML files, their expected rows in JSON files, and a command checks one against the other.

Tech stack: Python 3.13, `rdflib`, `psycopg`, `tomllib`, `random.Random`, `decimal`, Postgres
17.12.

Spec: `docs/superpowers/specs/2026-11-16-semantic-lab-design.md`, sections "The domain",
"Questions the system must answer" and item 2 of "Order of work". Read `AGENTS.md` and
`CODING_STANDARDS.md` first.

One change to the design's order: the seed needs concept keys, so the four taxonomy files and
`rdflib` arrive in this unit. Unit 3 keeps the ontology, the SHACL shapes and the mapping.
Task 6 writes that into the design.

## Global constraints

- Python 3.13 with `uv`. The one new runtime dependency is `rdflib`, which the design lists.
- Postgres is the system of record. Only the seed command writes it, and it rebuilds the
  lab's tables from nothing in one transaction.
- The generator is pure: no clock, no network, no file, no `hash()` or set order in anything
  that reaches a row. Randomness comes only from one `random.Random(seed)`.
- Money and weights are `Decimal`, dates are `datetime.date`.
- Every row is identified by its business code. There are no surrogate ids.
- IRIs start with `https://semantic-lab.example/`. `.example` is a reserved name, so they
  resolve nowhere on purpose.
- Names are English. Prose follows the humanizer rules. Commits carry no attribution line and
  are authored as `AndresRubio <2109109+AndresRubio@users.noreply.github.com>`.
- No command in this unit names `.env`: the owner's settings deny agents that file. Use
  `tests/stack.env` wherever a command needs settings.
- `domain/` imports only the standard library. `rdf/`, `seed/` and `evals/` import `domain/`
  and no other layer. `commands/` imports anything.
- Work happens on the branch `unit-2-domain-and-seed` and ends in a pull request the owner
  merges.

## Review focus

1. The seed command runs twice. The second run leaves the same rows as the first, with no
   duplicate and no error. Task 4.
2. Postgres is down or the password is wrong. The seed command prints one line, exits 1,
   shows no traceback and no credential. Task 5.
3. A taxonomy file is broken: a concept with no Spanish label, a `skos:broader` pointing
   nowhere, a cycle. Loading fails and names the concept, and the seed command stops before
   it touches the database. Tasks 1 and 5.
4. A reference query returns other columns than its question declares, or a question has no
   expected file. The questions command reports that question and exits 1. Task 6.
5. The same seed gives other rows on CI's Linux than on the Mac. A pinned digest of the
   dataset fails the offline suite. Task 3.

## The data model

Each line is a table. The generator's row types in `domain/records.py` have the same names in
CamelCase and the same fields.

```
concept(key pk, scheme, iri unique, label_en, label_es, parent_key -> concept, null at a root)
concept_alt_label(concept_key -> concept, lang, label; pk all three)
concept_closure(ancestor_key -> concept, descendant_key -> concept, depth; pk both keys)
cooperative(code pk, name, region_key -> concept)
cooperative_certification(cooperative_code, certification in ('organic','fair_trade'), valid_from, valid_until null; pk first three)
farm(code pk, name, cooperative_code, altitude_m)
shipment(code pk, origin_port, destination_port, departed_on, arrived_on)
lot(code pk, cooperative_code, shipment_code, process_key -> concept, variety, harvested_on, weight_kg numeric(10,2), price_per_kg numeric(8,2))
lot_farm(lot_code, farm_code; pk both)
product(code pk, name, category_key -> concept, bag_weight_g, list_price numeric(8,2))
product_flavour(product_code, flavour_key -> concept; pk both)
roast_batch(code pk, product_code, roasted_on, output_kg numeric(8,2), cost_per_kg numeric(8,2))
roast_batch_lot(roast_batch_code, lot_code, share numeric(3,2); pk both)
customer(code pk, name, segment in ('cafe','shop','restaurant'), city, country)
sales_order(code pk, customer_code, ordered_on)
order_line(order_code, line_no, product_code, roast_batch_code, bags, unit_price numeric(8,2), amount numeric(10,2), kg numeric(8,3); pk first two)
quality_incident(code pk, lot_code, kind in ('recall'), reported_on, description)
```

`concept_closure` holds every concept paired with itself at depth 0 and with each ancestor at
its distance.

Row counts and code formats, all exact: 15 cooperatives `C-01`, 120 farms `F-001` (8 per
cooperative), 80 shipments `S-01`, 600 lots `L-0001`, 40 products `P-01`, 3,000 roast batches
`B-0001`, 300 customers `K-001`, 20,000 orders `O-00001`, 60,000 order lines, 2 quality
incidents `Q-01`.

Definitions the questions rely on:
- The origin region of a lot is its cooperative's region, and the origin country is that
  region's parent concept.
- The revenue of an order line is `amount`, in euros. The revenue attributed to a lot is
  `amount` times that lot's `share` in the line's roast batch.
- The margin of an order line is `amount - kg * cost_per_kg` of its roast batch.
- A lot is organic when its cooperative holds an `organic` certification that covers
  `harvested_on`.

## The four taxonomies

One file per scheme in `ontology/taxonomy/`. Every concept has one `skos:notation` (its key),
one `skos:prefLabel` in `en` and one in `es`, one `skos:inScheme` and at most one
`skos:broader`. A key is `<scheme>.<slug>`, and the concept's IRI is
`https://semantic-lab.example/taxonomy/<scheme>#<slug>`. The scheme itself is the resource
`https://semantic-lab.example/taxonomy/<scheme>`, a `skos:ConceptScheme` whose `skos:notation`
is the scheme's name.

```
geo (33)       africa > ethiopia > yirgacheffe, sidama, guji, harrar
               africa > kenya > nyeri, kirinyaga, kiambu, embu
               south-america > colombia > huila, narino, cauca, tolima
               south-america > peru > cajamarca, cusco, junin, san-martin
               central-america > guatemala > antigua, huehuetenango, atitlan, coban
               central-america > honduras > copan, marcala, santa-barbara, el-paraiso
process (7)    washed · natural > anaerobic-natural · honey > yellow-honey, red-honey, black-honey
flavour (23)   fruity > berry > blackberry, raspberry
               fruity > citrus > orange, lemon
               fruity > stone-fruit > peach
               floral > jasmine, rose
               sweet > caramel, honey, chocolate > cocoa, dark-chocolate
               nutty > hazelnut, almond
               spicy > cinnamon
category (7)   coffee > single-origin > microlot
               coffee > blend > espresso-blend, filter-blend
               coffee > decaf
```

Labels the tests pin: `process.washed` is "Washed" in `en` and "Lavado" in `es`, with the
alternative label "wet process" in `en`. `process.natural` has "dry process" in `en`.
`flavour.fruity` is "Afrutado" in `es`. `geo.narino` is "Nariño" in both languages.

## File map

```
ontology/taxonomy/{geo,process,flavour,category}.ttl
src/semantic_lab/
  domain/errors.py       TaxonomyError
  domain/taxonomy.py     Concept, Taxonomy, build_taxonomy
  domain/records.py      one frozen dataclass per table, and Dataset
  rdf/taxonomy.py        load_taxonomy
  seed/planted.py        the planted facts as constants
  seed/supply.py         cooperatives, certifications, farms, shipments, lots, products
  seed/sales.py          roast batches, customers, orders, order lines, incidents
  seed/generate.py       generate, DEFAULT_SEED, digest
  seed/schema.sql        the 17 tables
  seed/load.py           rebuild
  evals/questions.py     Question, load, read_expected, to_json_rows
  evals/reference.py     run_sql
  commands/seed.py · commands/questions.py
questions/dev.toml · questions/heldout.toml · questions/expected/<id>.json
tests/ mirrors the above, plus guards/test_layers.py and guards/test_questions.py
```

## Task 1: the taxonomies

Files:
- Create: the four `.ttl` files, `src/semantic_lab/domain/{__init__,errors,taxonomy}.py`,
  `src/semantic_lab/rdf/{__init__,taxonomy}.py`, `tests/domain/{__init__,test_taxonomy}.py`,
  `tests/rdf/{__init__,test_taxonomy}.py`, `tests/guards/test_layers.py`
- Modify: `pyproject.toml` (add `rdflib`), `uv.lock`

Interfaces:
- Produces: `domain.errors.TaxonomyError(Exception)`;
  `domain.taxonomy.Concept`, frozen, with `key`, `scheme`, `iri`, `label_en`, `label_es`
  (all `str`), `alt_labels: tuple[tuple[str, str], ...]` as `(lang, label)` pairs, and
  `parent_key: str | None`;
  `domain.taxonomy.Taxonomy`, frozen, with `concepts: tuple[Concept, ...]` sorted by key and
  the methods `get(key) -> Concept` (raises `TaxonomyError` for an unknown key),
  `children(key)`, `descendants(key)` (the concept itself excluded), `in_scheme(scheme)`,
  `leaves(scheme)`, each returning `tuple[Concept, ...]` sorted by key, and
  `closure() -> tuple[tuple[str, str, int], ...]` as `(ancestor, descendant, depth)` sorted;
  `domain.taxonomy.build_taxonomy(concepts: Iterable[Concept]) -> Taxonomy`;
  `rdf.taxonomy.load_taxonomy(directory: Path) -> Taxonomy`.

- [ ] Step 1: create the branch `unit-2-domain-and-seed` from `main`. Add `rdflib` to the
  runtime dependencies and run `uv sync --extra dev`.
- [ ] Step 2: write the failing tests in `tests/domain/test_taxonomy.py`, on small hand-built
  concepts:

```python
def test_concepts_come_back_sorted_by_key(): ...
def test_children_descendants_and_leaves(): ...      # a > b > c, a > d: children(a) == (b, d), descendants(a) == (b, c, d), leaves == (c, d)
def test_closure_pairs_each_concept_with_itself_and_its_ancestors(): ...  # (a,a,0), (a,b,1), (a,c,2), (a,d,1), (b,b,0), (b,c,1), ...
def test_get_of_an_unknown_key_raises_taxonomy_error(): ...
@pytest.mark.parametrize(...)                         # each raises TaxonomyError naming the key:
def test_build_refuses(case): ...                     # duplicate key · parent not present · parent in another scheme · a cycle a > b > a · an empty label_en or label_es · a key that does not start with "<scheme>."
```

- [ ] Step 3: write the failing tests in `tests/rdf/test_taxonomy.py`:

```python
def test_the_four_files_load_to_70_concepts(): ...    # counts by scheme: geo 33, process 7, flavour 23, category 7
def test_the_pinned_labels(): ...                     # the four label facts from "The four taxonomies"
def test_every_iri_is_built_from_its_key(): ...       # process.red-honey -> https://semantic-lab.example/taxonomy/process#red-honey
def test_fruity_reaches_its_eight_descendants(): ...  # berry, blackberry, raspberry, citrus, orange, lemon, stone-fruit, peach
def test_every_region_has_a_country_and_a_continent(): ...  # the 24 leaves of geo are at depth 2
@pytest.mark.parametrize(...)                         # a tmp_path file with one fault each; TaxonomyError names the concept's IRI:
def test_a_broken_file_is_refused(case): ...          # no es prefLabel · two en prefLabels · no notation · two skos:broader · broader pointing at no concept · no inScheme
def test_an_empty_directory_is_refused(): ...
```

- [ ] Step 4: write the failing test in `tests/guards/test_layers.py`. It parses every file
  under `src/semantic_lab/` with `ast` and checks each `semantic_lab.<package>` import against
  this table: `domain` imports nothing of ours; `rdf`, `seed` and `evals` import only
  `domain`; `semantic` imports nothing of ours; `commands` may import anything; nothing
  imports `commands`. It also checks that `domain` imports no third-party module, against
  `sys.stdlib_module_names`.
- [ ] Step 5: run `uv run pytest tests/domain tests/rdf tests/guards/test_layers.py -q`.
  Expected: FAIL.
- [ ] Step 6: write the four Turtle files and implement the three modules. `load_taxonomy`
  parses every `*.ttl` in the directory into one `rdflib.Graph` and builds the concepts from
  `skos:Concept` subjects.
- [ ] Step 7: run the same tests, then `scripts/check.sh`. Expected: PASS.
- [ ] Step 8: commit, with this plan file: "Add the four taxonomies and the loader that
  reads them".

## Task 2: the supply side of the generator

Files:
- Create: `src/semantic_lab/domain/records.py`,
  `src/semantic_lab/seed/{__init__,planted,supply}.py`,
  `tests/seed/{__init__,conftest,test_supply}.py`

Interfaces:
- Consumes: `Taxonomy`, `load_taxonomy`.
- Produces: the record dataclasses of "The data model" (`Cooperative`,
  `CooperativeCertification`, `Farm`, `Shipment`, `Lot`, `LotFarm`, `Product`,
  `ProductFlavour`, `RoastBatch`, `RoastBatchLot`, `Customer`, `SalesOrder`, `OrderLine`,
  `QualityIncident`), each frozen;
  `planted.RECALLED_LOTS = ("L-0152", "L-0417")`, `planted.RECALL_DATES = {"L-0152":
  date(2024, 9, 5), "L-0417": date(2025, 3, 18)}`, `planted.LAPSED_COOPERATIVE = "C-07"`,
  `planted.LAPSE_DATE = date(2025, 6, 30)`, `planted.BLENDS = ("Alba", "Brisa")`,
  `planted.SHARED_FARMS = 3`, `planted.ALBA_POOL` (the lot codes `L-0001` to `L-0012`) and
  `planted.BRISA_POOL` (`L-0013` to `L-0024`);
  `supply.Supply`, frozen, with tuples `cooperatives`, `certifications`, `farms`, `shipments`,
  `lots`, `lot_farms`, `products`, `product_flavours`;
  `supply.generate_supply(taxonomy: Taxonomy, rng: random.Random) -> Supply`;
  the session fixture `taxonomy` in `tests/seed/conftest.py`.

What the tests pin, in `tests/seed/test_supply.py`:

```python
def test_counts_and_codes(): ...             # 15, 120, 80, 600, 40; first and last code of each; 8 farms per cooperative
def test_every_country_has_two_cooperatives_or_more(): ...
def test_a_lot_has_one_to_three_farms_all_from_its_cooperative(): ...
def test_lot_values_are_in_range(): ...      # harvested_on 2023-10-01..2025-09-30; weight_kg 600..3000; price_per_kg 4.00..14.00; process_key in the process scheme
def test_a_shipment_carries_lots_of_one_country_and_sails_after_their_harvest(): ...  # every shipment has a lot; departed_on > every harvested_on; arrived_on is 20..45 days after departed_on
def test_products(): ...                     # category_key is any category concept but the root; 28 are single-origin or microlot, 10 are blend, espresso-blend or filter-blend, 2 are decaf; "Alba" and "Brisa" are among the 10; 1..3 flavour notes, all leaves of flavour; bag_weight_g in (250, 1000); unique names
def test_enough_lots_arrive_before_roasting_starts(): ...   # 60 or more lots have arrived_on <= 2023-12-31, with every country among them
def test_the_blend_pools(): ...              # planted.ALBA_POOL and planted.BRISA_POOL are 12 lot codes each, disjoint; each pool's farms number 5 or more; the two farm sets share exactly planted.SHARED_FARMS; 4 or more lots of each pool arrive by 2023-12-31
def test_a_recalled_lot_arrives_60_days_or_more_before_its_recall(): ...
def test_the_lapsed_cooperative(): ...       # C-07 holds organic from 2022-01-01 until 2025-06-30; it has 5 or more lots harvested in 2025 on or before that date and 5 or more after it; 6 other cooperatives hold organic with no end
def test_the_recalled_lots_exist(): ...
def test_same_seed_same_supply_and_another_seed_differs(): ...
```

- [ ] Step 1: write `domain/records.py` and `seed/planted.py`, then the failing tests.
- [ ] Step 2: run `uv run pytest tests/seed -q`. Expected: FAIL.
- [ ] Step 3: implement `generate_supply`. Invented names for cooperatives, farms and
  products are the implementer's choice.
- [ ] Step 4: run the same tests, then `scripts/check.sh`. Expected: PASS.
- [ ] Step 5: commit: "Add the record types and the supply side of the generator".

## Task 3: the sales side, the dataset and its digest

Files:
- Create: `src/semantic_lab/seed/{sales,generate}.py`, `tests/seed/{test_sales,test_generate}.py`
- Modify: `src/semantic_lab/domain/records.py` (add `Dataset`), `tests/seed/conftest.py`

Interfaces:
- Consumes: `Supply`, `generate_supply`, `planted`.
- Produces: `records.Dataset`, frozen, with one tuple per data table in the order of "The
  data model" (the three concept tables excluded);
  `sales.Sales` and `sales.generate_sales(supply: Supply, rng: random.Random) -> Sales`;
  `generate.DEFAULT_SEED = 20240101`;
  `generate.generate(taxonomy: Taxonomy, seed: int) -> Dataset`;
  `generate.digest(dataset: Dataset) -> str`, the sha256 hex of every row's `repr`, table by
  table in the dataset's order;
  the session fixture `dataset` (the default seed) in `tests/seed/conftest.py`.

What the tests pin:

```python
# tests/seed/test_sales.py
def test_counts_and_codes(): ...             # 3,000 batches, 300 customers, 20,000 orders, 60,000 lines, 2 incidents
def test_a_single_origin_batch_has_one_lot_with_share_1(): ...
def test_a_blend_batch_has_two_to_four_lots_whose_shares_sum_to_exactly_1(): ...
def test_a_batch_is_roasted_in_range_and_after_its_lots_arrive(): ...   # 2024-01-02..2025-12-28
def test_cost_per_kg_follows_from_the_lots(): ...   # sum(share * price_per_kg) / Decimal("0.85"), rounded half up to cents
def test_every_product_has_a_batch_by_2024_01_05(): ...
def test_an_order_has_one_to_six_lines_with_distinct_products(): ...
def test_a_line_is_filled_from_a_batch_of_its_product_roasted_on_or_before_the_order(): ...
def test_line_arithmetic(): ...              # bags 1..40; amount == bags * unit_price; kg == bags * bag_weight_g / 1000
def test_orders_are_dated_2024_01_02_to_2025_12_31_and_every_month_has_orders(): ...
def test_each_recalled_lot_reaches_customers(): ...   # 3..6 batches consume it; lines from those batches reach 10..40 distinct customers; its incident is dated per planted.RECALL_DATES
def test_alba_and_brisa_share_exactly_three_farms(): ...   # and each draws on 5 or more farms

# tests/seed/test_generate.py
def test_every_reference_resolves(): ...     # every foreign key in "The data model" points at an existing row or concept
def test_same_seed_same_digest(): ...
def test_another_seed_another_digest(): ...
def test_the_default_digest_is_pinned():
    assert generate.digest(dataset) == PINNED
```

- [ ] Step 1: write the failing tests, with `PINNED = ""`.
- [ ] Step 2: run `uv run pytest tests/seed -q`. Expected: FAIL.
- [ ] Step 3: implement `sales.py` and `generate.py`. `generate` builds one
  `random.Random(seed)` and passes it to both sides. Alba's batches draw only from
  `planted.ALBA_POOL` and Brisa's only from `planted.BRISA_POOL`, which Task 2 built so their
  farms overlap in exactly three.
- [ ] Step 4: run the tests. When all but the pin pass, set `PINNED` to the digest the
  default seed gives, and run again. Expected: PASS. The full generation should take a few
  seconds at most; say so in the report if it takes longer.
- [ ] Step 5: run `scripts/check.sh`, then commit: "Add the sales side of the generator and
  pin the dataset's digest".

## Task 4: the schema and the loader

Files:
- Create: `src/semantic_lab/seed/{schema.sql,load.py}`, `tests/seed/test_load_db.py`
- Modify: `tests/conftest.py` (add the `seeded` fixture)

Interfaces:
- Consumes: `Taxonomy`, `Dataset`, `generate`, `load_taxonomy`.
- Produces: `load.TABLES: tuple[str, ...]`, the 17 table names in creation order;
  `load.rebuild(connection: psycopg.Connection[Any], taxonomy: Taxonomy, dataset: Dataset)
  -> dict[str, int]`, which drops and recreates the 17 tables and fills them with `COPY`, all
  in one transaction, and returns the row count of each;
  the session fixture `seeded(stack) -> Settings` in `tests/conftest.py`, which loads the
  repository's taxonomies, generates with `DEFAULT_SEED` and rebuilds once.

`schema.sql` declares the primary keys, foreign keys and `check` constraints of "The data
model", and an index on each foreign key of `order_line`, `roast_batch_lot` and `lot`.

- [ ] Step 1: write the failing tests in `tests/seed/test_load_db.py`, marked `db`:

```python
def test_every_table_holds_its_rows(seeded): ...        # count(*) per table equals the dataset's tuple length; concept 70; concept_closure equals len(taxonomy.closure())
def test_money_and_dates_survive_the_round_trip(seeded): ...   # one order line and one lot read back equal to their records, as Decimal and date
def test_a_second_rebuild_leaves_the_same_rows(seeded): ...    # rebuild again on a new connection; same counts; sum(amount) unchanged
def test_a_failed_rebuild_keeps_the_old_rows(seeded): ...      # a dataset with one order line pointing at a missing batch raises; counts are unchanged afterwards
def test_fruity_revenue_can_be_read_through_the_closure(seeded): ...   # a join on concept_closure with ancestor_key = 'flavour.fruity' returns rows
```

- [ ] Step 2: run `uv run pytest -m db tests/seed -q`. Expected: FAIL.
- [ ] Step 3: write `schema.sql` and `load.py`. `load.py` reads the SQL with
  `importlib.resources`.
- [ ] Step 4: run `uv run pytest -m db -q`. Expected: PASS, the unit 1 `db` tests included.
- [ ] Step 5: run `scripts/check.sh`, then commit: "Add the Postgres schema and the loader
  that rebuilds it".

## Task 5: the seed command

Files:
- Create: `src/semantic_lab/commands/seed.py`, `tests/commands/{test_seed,test_seed_db}.py`

Interfaces:
- Consumes: `config.load`, `load_taxonomy`, `generate`, `rebuild`.
- Produces: `seed.main(argv: Sequence[str], env: Mapping[str, str], out: TextIO, err:
  TextIO) -> int`. Arguments: `--seed N` (default `DEFAULT_SEED`) and `--taxonomy-dir PATH`
  (default `ontology/taxonomy`). It loads the taxonomy and generates before it connects. On
  success it prints one line per table, `<table>  <rows>`, in `load.TABLES` order, and
  returns 0. It returns 2 after `missing setting: <NAME>` on `err`, and 1 after one line on
  `err` for a `TaxonomyError` (`taxonomy: <message>`) or a database error (`postgres:` and
  the detail built the way `probes.py` builds one, with the password blanked).

- [ ] Step 1: write the failing tests:

```python
# tests/commands/test_seed.py
def test_a_missing_setting_exits_2_and_names_it(): ...
def test_a_broken_taxonomy_exits_1_before_any_connection(): ...   # --taxonomy-dir at a tmp_path with a faulty file; DSN on 127.0.0.1:1; err starts "taxonomy: "
def test_postgres_down_exits_1_with_one_line_and_no_password(): ...   # err is one line starting "postgres: "; the DSN's password is not in out or err

# tests/commands/test_seed_db.py, marked db
def test_seed_prints_17_lines_and_fills_the_tables(stack): ...   # exit 0; the order_line line ends in 60000
def test_seed_twice_gives_the_same_output(stack): ...
```

- [ ] Step 2: run them. Expected: FAIL.
- [ ] Step 3: implement `commands/seed.py`, with the one `if __name__ == "__main__"` block.
  If `probes.py`'s failure helper has to be shared, move it to a small module both import and
  keep `probes`' behaviour and tests unchanged.
- [ ] Step 4: run `uv run pytest tests/commands -q` and `uv run pytest -m db tests/commands
  -q`, then `scripts/check.sh`. Expected: PASS.
- [ ] Step 5: commit: "Add the seed command".

## Task 6: the first questions

Files:
- Create: `src/semantic_lab/evals/{__init__,questions,reference}.py`,
  `src/semantic_lab/commands/questions.py`, `questions/dev.toml`, `questions/heldout.toml`,
  `questions/expected/*.json`, `tests/evals/{__init__,test_questions}.py`,
  `tests/guards/test_questions.py`, `tests/commands/{test_questions,test_questions_db}.py`

Interfaces:
- Produces: `questions.KINDS = ("metric", "path", "hierarchy", "mixed")`;
  `questions.Question`, frozen, with `id`, `kind`, `text`, `columns: tuple[str, ...]`,
  `key: tuple[str, ...]`, `ordered: bool`, `sql: str`;
  `questions.QuestionError(Exception)`;
  `questions.load(path: Path) -> tuple[Question, ...]`;
  `questions.read_expected(directory: Path, question_id: str) -> list[list[object]]`;
  `questions.to_json_rows(rows: Iterable[Sequence[object]]) -> list[list[object]]`, which
  turns a `Decimal` into an `int` when it is whole and a `float` otherwise, and a `date` into
  its ISO string;
  `reference.run_sql(connection, question) -> list[list[object]]`, which raises
  `QuestionError` when the query's column names differ from `question.columns`, and sorts the
  rows by the key columns unless `ordered` is true;
  `commands.questions.main(argv, env, out, err) -> int`: with no argument it prints `ok
  <id>`, `DRIFT <id>`, `MISSING <id>` or `ERROR <id>  <reason>` per question and returns 1
  unless all are ok; with `--write-expected` it writes each `questions/expected/<id>.json` as
  `{"rows": [...]}` and returns 0. `--questions-dir` defaults to `questions`.

A question in TOML:

```toml
[[question]]
id = "metric-revenue-by-country-2025"
kind = "metric"
text = "What was the revenue in 2025 for each origin country? Give the country and the revenue in euros."
columns = ["country", "revenue"]
key = ["country"]
ordered = false
sql = """
select ...
"""
```

The twelve questions. Each `text` names its columns and uses the definitions of "The data
model". A country, continent, process or flavour is given by its English label.

| File | id | Asks for | columns |
|---|---|---|---|
| dev | `metric-revenue-by-country-2025` | 2025 revenue by origin country | country, revenue |
| dev | `metric-revenue-by-quarter-2025` | 2025 revenue per quarter, as `2025-Q1` | quarter, revenue |
| dev | `metric-top-customers-kg-2025` | the five customers with the most kilograms in 2025, largest first | customer, kg |
| dev | `metric-orders-by-segment-2024` | number of orders in 2024 per customer segment | segment, orders |
| dev | `metric-organic-lots-2025` | how many lots harvested in 2025 were organic | lots |
| dev | `hierarchy-kg-fruity-2025` | kilograms sold in 2025 of products with a fruity note or any note under it, each line counted once | kg |
| dev | `hierarchy-revenue-by-continent-2025` | 2025 revenue by origin continent | continent, revenue |
| dev | `hierarchy-margin-by-process-2025` | 2025 margin attributed to lots, grouped under washed, natural and honey | process, margin |
| heldout | `metric-revenue-by-country-2024-q4` | revenue by origin country from October to December 2024 | country, revenue |
| heldout | `metric-average-order-value-by-segment-2025` | average order value in 2025 per segment, to the cent | segment, average_order_value |
| heldout | `hierarchy-kg-honey-process-2024` | kilograms sold in 2024 attributed to lots of the honey process or any grade under it | kg |
| heldout | `hierarchy-revenue-floral-by-quarter-2025` | 2025 revenue per quarter of products with a floral note or any note under it | quarter, revenue |

- [ ] Step 1: write the failing offline tests:

```python
# tests/evals/test_questions.py
def test_load_reads_a_question(): ...
@pytest.mark.parametrize(...)   # each raises QuestionError naming the id:
def test_load_refuses(case): ...   # a duplicate id · a kind outside KINDS · a key column missing from columns · empty text · empty sql · no columns
def test_to_json_rows(): ...       # Decimal("12.50") -> 12.5, Decimal("3") -> 3, date(2025, 3, 18) -> "2025-03-18", text unchanged
def test_read_expected_of_a_missing_file_raises_question_error(): ...

# tests/guards/test_questions.py
def test_ids_are_unique_across_both_files(): ...
def test_every_question_has_an_expected_file_and_no_file_is_orphaned(): ...
def test_every_expected_row_has_one_value_per_column_and_at_most_200_rows(): ...
def test_there_are_eight_dev_and_four_heldout_questions_or_more(): ...

# tests/commands/test_questions.py
def test_a_missing_setting_exits_2(): ...
```

- [ ] Step 2: write the failing `db` tests in `tests/commands/test_questions_db.py`:

```python
def test_the_stored_answers_match_the_seeded_database(seeded): ...   # main([]) returns 0 and prints "ok" for all twelve
def test_drift_is_reported(seeded, tmp_path): ...       # a copy of questions/ with one expected value changed -> "DRIFT <id>", exit 1
def test_a_missing_expected_file_is_reported(seeded, tmp_path): ...   # "MISSING <id>", exit 1
def test_wrong_columns_are_reported(seeded, tmp_path): ...   # a question whose sql returns another column name -> "ERROR <id>", exit 1
def test_the_fruity_question_counts_each_line_once(seeded): ...   # its kg equals a direct count over distinct order lines, and is below the sum of a join that fans out
```

- [ ] Step 3: run both sets. Expected: FAIL.
- [ ] Step 4: implement the two `evals` modules and the command, and write the twelve
  questions with their reference SQL.
- [ ] Step 5: produce the expected files against the test stack, with no `.env`:

```bash
docker compose -p semantic-lab-test -f compose.yaml --env-file tests/stack.env up -d
uv run --env-file tests/stack.env python -m semantic_lab.commands.smoke --no-model   # repeat until three ok lines
uv run --env-file tests/stack.env python -m semantic_lab.commands.seed
uv run --env-file tests/stack.env python -m semantic_lab.commands.questions --write-expected
docker compose -p semantic-lab-test -f compose.yaml --env-file tests/stack.env down -v
```

  Read each expected file and check it is plausible: six countries, four quarters, three
  segments, no empty result, no zero total.
- [ ] Step 6: run `uv run pytest -n auto -m "not db and not model"`, `uv run pytest -m db` and
  `scripts/check.sh`. Expected: PASS.
- [ ] Step 7: commit: "Add the first twelve questions with their reference SQL and answers".

## Task 7: the documents, the review and the pull request

Files:
- Modify: `AGENTS.md`, `CODING_STANDARDS.md`, `README.md`,
  `docs/superpowers/specs/2026-11-16-semantic-lab-design.md`,
  `docs/superpowers/specs/measured-facts.md`

- [ ] Step 1: in the design's "Order of work", say that unit 2 also brings the four taxonomy
  files and `rdflib`, because the seed needs concept keys, and that unit 3 keeps the
  ontology, the SHACL shapes and the mapping. In "The domain", replace the sentence about
  regions pointing at concept keys with what was built: a cooperative points at its region.
- [ ] Step 2: in `AGENTS.md`, add the seed command `[writes]` and the questions command
  (`[read-only]`, and `[writes]` with `--write-expected`), written with
  `uv run --env-file .env`, move `domain/`, `rdf/`, `seed/`, `evals/`, `ontology/taxonomy/`
  and `questions/` out of "planned", and say that a change to the generator changes the
  pinned digest and the expected answers, which are then produced again with the commands of
  Task 6, Step 5.
- [ ] Step 3: in `CODING_STANDARDS.md`, write the import table that `tests/guards/test_layers.py`
  checks, with the reason for each line, and add `rdflib` to the runtime dependencies.
- [ ] Step 4: in `measured-facts.md`, record, measured on the test stack: the seconds the
  seed command takes, the size of the Postgres volume or of the database
  (`select pg_size_pretty(pg_database_size(current_database()))`), and Postgres's memory
  after the load. Update the README's Status section.
- [ ] Step 5: run `scripts/check.sh --force`, `uv run pytest -n auto -m "not db and not
  model"` and `uv run pytest -m db`. Expected: all pass. Commit: "Record what unit 2 built
  in the design, the instructions and the measured facts".
- [ ] Step 6: a fresh agent reviews the branch against `CODING_STANDARDS.md`, this plan and
  the design. Fix what it finds and rerun Step 5.
- [ ] Step 7: push the branch and open a pull request against `main`. Check the three CI
  jobs. The owner merges.
