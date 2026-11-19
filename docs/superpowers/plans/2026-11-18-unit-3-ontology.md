# Unit 3, the ontology, its shapes and the mapping: implementation plan

> For agentic workers: REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task by task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

Goal: the Cumbre Coffee domain gets its one written definition, an ontology in RDFS and OWL
with SHACL shapes, a mapping file that says where each term lives in Postgres, and one command
that proves the ontology, the taxonomies, the mapping and the generated rows agree.

Architecture: three hand-written files sit in `ontology/` beside the taxonomies:
`ontology.ttl`, `shapes.ttl` and `mapping.yaml`. `rdf/` reads each one into a plain value kept
in `domain/`, exports the generator's rows as RDF through the mapping, and validates graphs
with `pyshacl`. A read-only command wires them together and needs no database.

Tech stack: Python 3.13, `rdflib` 7.6.0, `pyshacl` 0.40.2, `pyyaml` 6.0.3, SHACL core plus
SHACL-SPARQL constraints.

Spec: `docs/superpowers/specs/2026-11-16-semantic-lab-design.md`, sections "Four terms as
this repo uses them", "The domain", "Architecture" (the three checks) and item 3 of "Order of
work". Read `AGENTS.md` and `CODING_STANDARDS.md` first.

What this unit leaves out, on purpose. The design's mapping names three stores per term. Unit
3 writes the Postgres target only, because the Neo4j labels are unit 4's decision and the Cube
members are unit 5's. Each of those units adds its key to every entry and its own check. Task
7 writes that into the design.

## Global constraints

- Python 3.13 with `uv`. Two new runtime dependencies, both listed in the design's
  Conventions: `pyshacl` and `pyyaml`. One new development dependency: `types-PyYAML`, so mypy
  can check the YAML reader. No other dependency.
- The generator's rows do not change. The pinned digest in `tests/seed/test_generate.py` and
  the twelve files in `questions/expected/` stay byte for byte as they are.
- `domain/` imports only the standard library. `rdf/` imports `domain/` and no other layer.
  `tests/guards/test_layers.py` already enforces both.
- Every IRI starts with `https://semantic-lab.example/`. The ontology's namespace is
  `https://semantic-lab.example/ontology#` with the prefix `sl:`, the shapes use
  `https://semantic-lab.example/shapes#` with the prefix `shape:`, and exported rows live
  under `https://semantic-lab.example/data/`.
- No OWL reasoner and no RDFS inference run anywhere. `pyshacl` is called with
  `inference="none"`, and the only reasoning is SHACL's own: a shape that targets a class also
  targets its subclasses when the ontology graph is passed as `ont_graph`.
- No command in this unit names `.env`: the owner's settings deny agents that file. Use
  `tests/stack.env` wherever a command needs settings.
- Names are English. Prose follows the humanizer rules. Comments and docstrings are short:
  they keep the reason and drop the history.
- Commits are one plain sentence, carry no attribution line and are authored as
  `AndresRubio <2109109+AndresRubio@users.noreply.github.com>`. `scripts/check.sh` passes
  before each commit.
- One writing agent per checkout at a time. A reviewer may run beside a writer.
- `uv run pytest -m db` runs without `-n`, one run per machine. The containers
  `boe-demo-db-1` and `boe-agent-db-1` are not ours: leave them.
- Work happens on the branch `unit-3-ontology` and ends in a pull request the owner merges.

## Measured before planning

Run on 2026-11-18 on the owner's Mac, outside the project's environment, so `pyproject.toml`
and `uv.lock` are untouched.

- `pyshacl` 0.40.2 ships a `py.typed` marker. PyYAML 6.0.3 does not, and `types-PyYAML`
  supplies its stubs.
- With the ontology passed as `ont_graph` and `inference="none"`, a shape with
  `sh:targetClass sl:Product` reported a node typed only `sl:SingleLotProduct`. The data graph
  was not changed by the call.
- These features worked as the SHACL specification says: `sh:closed`, `sh:pattern`,
  `sh:lessThan` on two `xsd:date` values, `sh:equals` on a sequence path, a sequence path with
  `sh:zeroOrMorePath`, `sh:inversePath`, `sh:node`, `sh:targetSubjectsOf`, and `sh:sparql`
  with `GROUP BY` and `HAVING`. A SPARQL `SUM` over `xsd:decimal` shares 0.33, 0.33 and 0.34
  compared equal to 1.
- A plain string literal satisfies `sh:datatype xsd:string`. `rdflib` writes a `Decimal` as
  `xsd:decimal` with its scale kept, an `int` as `xsd:integer` and a `date` as `xsd:date`.
- A malformed shape (`sh:minCount "many"`) raises `pyshacl.errors.ConstraintLoadError`, a
  subclass of `pyshacl.errors.ReportableRuntimeError`, as are `ShapeLoadError` and
  `ValidationFailure`.
- A rough export of the default seed with five shapes: the first 200 orders with every
  supply row and every batch gave 51,317 triples and validated in 0.43 s. All 60,000 order
  lines gave 664,730 triples and validated in 16.37 s. So the offline suite validates a
  sample, and the full dataset runs only when the command is asked for it.
- For the seeds 20240101, 1, 7 and 99, every rule the data shapes below state held on the
  generated rows, checked in plain Python: dates in order, shares summing to 1, one component
  for a one-lot batch and two to four for a blend, lots from the product's region, no batch
  oversold, farms in the lot's cooperative, the code formats and the positive amounts.
- The SHACL features `sh:xone`, `sh:uniqueLang`, `sh:languageIn`, `sh:in` and `sh:or` were
  not probed in a failing case. The fault tables of Tasks 3 and 6 are their first test.

## Review focus

1. A class or property is added to the ontology and nobody adds its mapping entry, or a
   column is added to a record and no property maps it. The mapping check names the term or
   the column. Task 4.
2. A shape's target is misspelt, so it matches nothing and every graph passes. Each rule in
   the shapes file has a faulty example that it must report, and each data class must have a
   closed shape that targets it. Tasks 3 and 6.
3. A file in `ontology/` is broken: bad Turtle, bad YAML, a missing file, a shape `pyshacl`
   cannot load. The command prints one line, exits 1 and shows no traceback. Tasks 1, 3, 4
   and 7.
4. A null reaches the export. A blend's missing origin region or an open-ended certification
   gives no triple at all, never the text `None`. Task 5.
5. The command's output differs between two runs or between the Mac and CI, because `rdflib`
   returns triples in set order. Violations are sorted before anything prints. Tasks 3 and 7.

## The ontology's terms

Fourteen classes. `Blend` and `SingleLotProduct` are subclasses of `Product`, and no other
class has a parent. Country and region get no class: they are concepts of the geography
taxonomy, so a property that points at one has `skos:Concept` as its range. RDF has no
properties on a relation, so the share of a lot in a roast batch is a class of its own,
`BatchComponent`.

| Class | Table | Key columns |
|---|---|---|
| `sl:Cooperative` | `cooperative` | `code` |
| `sl:Certification` | `cooperative_certification` | `cooperative_code`, `certification`, `valid_from` |
| `sl:Farm` | `farm` | `code` |
| `sl:Shipment` | `shipment` | `code` |
| `sl:Lot` | `lot` | `code` |
| `sl:Product` | `product` | `code` |
| `sl:Blend` | `product`, when `category_key` is `category.blend` or under it | as `sl:Product` |
| `sl:SingleLotProduct` | `product`, when `category_key` is `category.single-origin` or `category.decaf` or under one of them | as `sl:Product` |
| `sl:RoastBatch` | `roast_batch` | `code` |
| `sl:BatchComponent` | `roast_batch_lot` | `roast_batch_code`, `lot_code` |
| `sl:Customer` | `customer` | `code` |
| `sl:Order` | `sales_order` | `code` |
| `sl:OrderLine` | `order_line` | `order_code`, `line_no` |
| `sl:QualityIncident` | `quality_incident` | `code` |

Eighteen object properties, each with exactly one `rdfs:domain` and one `rdfs:range`.

| Property | Domain | Range | Postgres |
|---|---|---|---|
| `sl:inRegion` | `Cooperative` | `skos:Concept` | `cooperative.region_key` |
| `sl:memberOf` | `Farm` | `Cooperative` | `farm.cooperative_code` |
| `sl:heldBy` | `Certification` | `Cooperative` | `cooperative_certification.cooperative_code` |
| `sl:producedBy` | `Lot` | `Cooperative` | `lot.cooperative_code` |
| `sl:harvestedFrom` | `Lot` | `Farm` | link `lot_farm`, from `lot_code` to `farm_code` |
| `sl:shippedIn` | `Lot` | `Shipment` | `lot.shipment_code` |
| `sl:process` | `Lot` | `skos:Concept` | `lot.process_key` |
| `sl:category` | `Product` | `skos:Concept` | `product.category_key` |
| `sl:originRegion` | `Product` | `skos:Concept` | `product.origin_region_key` |
| `sl:flavourNote` | `Product` | `skos:Concept` | link `product_flavour`, from `product_code` to `flavour_key` |
| `sl:batchOf` | `RoastBatch` | `Product` | `roast_batch.product_code` |
| `sl:componentOf` | `BatchComponent` | `RoastBatch` | `roast_batch_lot.roast_batch_code` |
| `sl:fromLot` | `BatchComponent` | `Lot` | `roast_batch_lot.lot_code` |
| `sl:placedBy` | `Order` | `Customer` | `sales_order.customer_code` |
| `sl:lineOf` | `OrderLine` | `Order` | `order_line.order_code` |
| `sl:sells` | `OrderLine` | `Product` | `order_line.product_code` |
| `sl:fromBatch` | `OrderLine` | `RoastBatch` | `order_line.roast_batch_code` |
| `sl:affects` | `QualityIncident` | `Lot` | `quality_incident.lot_code` |

Thirty-two datatype properties. `sl:code` and `sl:name` are shared by several classes, and
several `rdfs:domain` statements would mean their intersection, so those two declare no
domain and the shapes say which classes carry them. Every other one has exactly one domain,
the class of its table. Ranges are `xsd:string`, `xsd:integer`, `xsd:decimal` or `xsd:date`.

| Range | Properties and their columns |
|---|---|
| `xsd:string` | `sl:code` (the `code` column of `cooperative`, `farm`, `shipment`, `lot`, `product`, `roast_batch`, `customer`, `sales_order` and `quality_incident`), `sl:name` (the `name` column of `cooperative`, `farm`, `product` and `customer`), `sl:standard` (`cooperative_certification.certification`), `sl:originPort`, `sl:destinationPort`, `sl:variety`, `sl:segment`, `sl:city`, `sl:country`, `sl:kind`, `sl:description` |
| `xsd:integer` | `sl:altitudeMetres` (`farm.altitude_m`), `sl:bagWeightGrams` (`product.bag_weight_g`), `sl:lineNo`, `sl:bags` |
| `xsd:decimal` | `sl:weightKg`, `sl:pricePerKg`, `sl:listPrice`, `sl:outputKg`, `sl:costPerKg`, `sl:share`, `sl:unitPrice`, `sl:amount`, `sl:kg` |
| `xsd:date` | `sl:validFrom`, `sl:validUntil`, `sl:departedOn`, `sl:arrivedOn`, `sl:harvestedOn`, `sl:roastedOn`, `sl:orderedOn`, `sl:reportedOn` |

Where no column is given, the property is the camelCase form of its one column, in the table
whose record has that field in `domain/records.py`. Together the 50 properties cover each of
the 63 columns of the 14 data tables exactly once.

Every class and property has one `rdfs:label` in English, one in Spanish and one
`rdfs:comment` in English that defines it in a sentence. The file's header is the resource
`https://semantic-lab.example/ontology`, an `owl:Ontology`.

## The mapping file

```yaml
classes:
  sl:Cooperative:
    postgres: {table: cooperative, key: [code]}
  sl:Blend:
    postgres:
      table: product
      key: [code]
      when: {column: category_key, under: [category.blend]}
properties:
  sl:name:
    postgres: {columns: [cooperative.name, farm.name, product.name, customer.name]}
  sl:harvestedFrom:
    postgres: {link: {table: lot_farm, from: lot_code, to: farm_code}}
```

A term is written with the `sl:` prefix and the reader expands it. A class entry names its
table and key columns, and `when` makes it conditional: the row is of that class when the
concept key in `column` is one of the `under` keys or a descendant of one. A property entry
has either `columns`, each a `table.column` on a class's table, or one `link`, a table with no
class of its own whose `from` column identifies the subject and whose `to` column the object.
The `postgres:` level exists because units 4 and 5 add `neo4j:` and `cube:` beside it.

## The exported RDF

A row of a class's table becomes one node. Its IRI is
`https://semantic-lab.example/data/<slug>/<key>`, where the slug is the class's local name in
kebab case (`order-line`, `batch-component`, `quality-incident`) and the key is the values of
the key columns, each percent-encoded, joined with `/`:
`.../data/order-line/O-00001/1`, `.../data/certification/C-07/organic/2023-01-01`. The node
gets one `rdf:type` for its unconditional class and one more for each conditional class whose
`when` holds. A column mapped by a datatype property gives a typed literal. A column mapped by
an object property gives the node of the range class with that key, or the concept's IRI when
the range is `skos:Concept`. A row of a link table gives one triple. A null gives nothing.

## The shapes

`ontology/shapes.ttl` holds three groups. Its header is the resource
`https://semantic-lab.example/shapes`, which carries the `sh:declare` prefix declarations
(`sl`, `skos`, `rdf`) that the SPARQL constraints name with `sh:prefixes`.

Taxonomy shapes:
- `shape:Concept` targets `skos:Concept`: exactly one `skos:notation`; `skos:prefLabel` in
  `en` and `es` only, unique per language, exactly two; `skos:altLabel` in `en` and `es`
  only; exactly one `skos:inScheme`, a `skos:ConceptScheme`; at most one `skos:broader`, a
  `skos:Concept`; and by SPARQL, the IRI equals
  `https://semantic-lab.example/taxonomy/<scheme>#<slug>` for the notation `<scheme>.<slug>`.
- `shape:ConceptScheme` targets `skos:ConceptScheme`: exactly one `skos:notation` and the
  same two labels.
- `shape:TypedSkos`: a subject of `skos:broader` or `skos:inScheme` is a `skos:Concept`, and
  a subject of `skos:notation` or `skos:prefLabel` is a `skos:Concept` or a
  `skos:ConceptScheme`. The Python loader finds concepts by their type, so an untyped concept
  would otherwise vanish without a word.

Ontology shapes:
- `shape:Class` targets `owl:Class`: an IRI in the ontology's namespace; the two labels and a
  comment; at most one `rdfs:subClassOf`, an `owl:Class`.
- `shape:ObjectProperty` targets `owl:ObjectProperty`: the labels and comment; exactly one
  `rdfs:domain`, an `owl:Class`; exactly one `rdfs:range`, an `owl:Class` or `skos:Concept`.
- `shape:DatatypeProperty` targets `owl:DatatypeProperty`: the labels and comment; at most
  one `rdfs:domain`; exactly one `rdfs:range`, one of the four XSD types.

Data shapes, one per class, named `shape:<Class>`. Every one except `shape:Blend` and
`shape:SingleLotProduct` is closed, with `rdf:type` ignored. A property is required exactly
once unless a line says otherwise, a datatype property has its `sh:datatype`, and an object
property whose range is a class has `sh:class`.

| Shape | Rules beyond the defaults |
|---|---|
| `Cooperative` | `code` matches `^C-[0-9]{2}$`; `inRegion` conforms to `shape:Region` |
| `Certification` | `standard` is `organic` or `fair_trade`; `validUntil` is optional; `validFrom` is less than `validUntil` |
| `Farm` | `code` matches `^F-[0-9]{3}$`; `altitudeMetres` is above 0 |
| `Shipment` | `code` matches `^S-[0-9]{2}$`; `departedOn` is less than `arrivedOn` |
| `Lot` | `code` matches `^L-[0-9]{4}$`; `process` conforms to `shape:ProcessConcept`; `weightKg` and `pricePerKg` are above 0; `harvestedFrom` at least once; the cooperatives of its farms (the path `harvestedFrom`, `memberOf`) equal `producedBy` |
| `Product` | `code` matches `^P-[0-9]{2}$`; `category` conforms to `shape:CategoryConcept`; `originRegion` is optional and conforms to `shape:Region`; `flavourNote` at least once, each conforming to `shape:FlavourConcept`; `bagWeightGrams` and `listPrice` are above 0; the node is exactly one of `sl:Blend` and `sl:SingleLotProduct` (`sh:xone`) |
| `Blend` | no `originRegion`; its category is `category:blend` or under it (the path `category`, then zero or more `skos:broader`, has that value) |
| `SingleLotProduct` | exactly one `originRegion` |
| `RoastBatch` | `code` matches `^B-[0-9]{4}$`; `outputKg` and `costPerKg` are above 0; at least one component points at it (inverse of `componentOf`); four SPARQL rules, below |
| `BatchComponent` | `share` is above 0 and at most 1 |
| `Customer` | `code` matches `^K-[0-9]{3}$`; `segment` is `cafe`, `shop` or `restaurant` |
| `Order` | `code` matches `^O-[0-9]{5}$`; at least one line points at it (inverse of `lineOf`) |
| `OrderLine` | `lineNo` and `bags` are at least 1; `unitPrice`, `amount` and `kg` are above 0; the product of its batch (the path `fromBatch`, `batchOf`) equals `sells` |
| `QualityIncident` | `code` matches `^Q-[0-9]{2}$`; `kind` is `recall` |

The four SPARQL rules of `shape:RoastBatch`, each a sentence from the design's domain:
1. The shares of its components sum to 1.
2. Its order lines do not sum to more kilograms than `outputKg`.
3. A batch of a `sl:SingleLotProduct` has exactly one component, and a batch of a `sl:Blend`
   has at least two.
4. When its product has an origin region, every lot it uses comes from a cooperative in that
   region.

Rule 1 as it was verified, the pattern for the others:

```turtle
sh:sparql [
  sh:message "The shares of a roast batch's components must sum to 1." ;
  sh:prefixes <https://semantic-lab.example/shapes> ;
  sh:select """
    SELECT $this (SUM(?share) AS ?value)
    WHERE { ?component sl:componentOf $this ; sl:share ?share . }
    GROUP BY $this
    HAVING (SUM(?share) != 1)
  """ ] ;
```

Four helper shapes have no target and are reached through `sh:node`. Each requires a
`skos:Concept` in one scheme: `shape:Region` (the geography scheme, with a value two
`skos:broader` steps up and none three steps up), `shape:ProcessConcept`,
`shape:CategoryConcept` (with a `skos:broader`, so never the root) and `shape:FlavourConcept`
(a leaf: nothing has it as `skos:broader`).

## File structure

```
ontology/ontology.ttl                  the 14 classes and 50 properties
ontology/shapes.ttl                    the three groups of shapes
ontology/mapping.yaml                  one entry per class and property
src/semantic_lab/domain/errors.py      + OntologyError, MappingError
src/semantic_lab/domain/records.py     + DATA_TABLES (moved from seed/load.py), record_type, rows
src/semantic_lab/domain/ontology.py    Ontology, OntologyClass, Property, build_ontology
src/semantic_lab/domain/mapping.py     Mapping and its entries, problems
src/semantic_lab/domain/sample.py      first_orders
src/semantic_lab/rdf/turtle.py         read: Turtle files into one graph, one error line
src/semantic_lab/rdf/taxonomy.py       + taxonomy_graph, taxonomy_of
src/semantic_lab/rdf/ontology.py       ontology_graph, ontology_of
src/semantic_lab/rdf/shacl.py          Violation, shapes_graph, validate
src/semantic_lab/rdf/mapping.py        load_mapping
src/semantic_lab/rdf/export.py         export
src/semantic_lab/commands/ontology.py  the check command
tests/                                 one mirror file each, plus tests/guards/test_shapes.py
```

Session fixtures for the repository's own files live in `tests/conftest.py`. Task 1 moves
`taxonomy` and `dataset` there, and each later task adds the one it produces: `ontology`
(Task 2), `shapes` (Task 3) and `mapping` (Task 4).

---

### Task 1: dependencies, one Turtle reader and the table list in `domain/`

Files:
- Modify: `pyproject.toml`, `uv.lock`, `src/semantic_lab/domain/errors.py`,
  `src/semantic_lab/domain/records.py`, `src/semantic_lab/seed/load.py`,
  `src/semantic_lab/rdf/taxonomy.py`, `tests/seed/test_load.py`, `tests/seed/conftest.py`,
  `tests/conftest.py`
- Create: `src/semantic_lab/rdf/turtle.py`, `tests/rdf/test_turtle.py`,
  `tests/domain/test_records.py`

Interfaces produced:

```python
# domain/errors.py
class OntologyError(Exception): ...   # the ontology or the shapes file is malformed
class MappingError(Exception): ...    # the mapping file is malformed or cannot be applied

# domain/records.py
DATA_TABLES: tuple[tuple[str, str], ...]              # (table, Dataset attribute), creation order
def record_type(table: str) -> type[Any]              # KeyError for a name that is no data table
def rows(dataset: Dataset, table: str) -> tuple[Any, ...]

# rdf/turtle.py
def read(files: Sequence[Path], error: type[Exception]) -> Graph

# rdf/taxonomy.py
def taxonomy_graph(directory: Path) -> Graph          # raises TaxonomyError
def taxonomy_of(graph: Graph) -> Taxonomy
def load_taxonomy(directory: Path) -> Taxonomy        # unchanged behaviour: the two composed
```

- [ ] Step 1: add `"pyshacl>=0.40.2"` and `"pyyaml>=6.0.3"` to `dependencies` and
  `"types-PyYAML"` to the `dev` extra. Run `uv lock`, then `uv sync --extra dev`, then
  `uv run mypy`. Expected: mypy reports no issue.
- [ ] Step 2: write `tests/rdf/test_turtle.py`, failing:

```python
def test_two_files_become_one_graph(tmp_path): ...        # len(graph) is the sum of both
def test_a_broken_file_raises_the_given_error(tmp_path):
    with pytest.raises(OntologyError, match=r"broken\.ttl: not valid Turtle") as refused:
        turtle.read([tmp_path / "broken.ttl"], OntologyError)
    assert "\n" not in str(refused.value) and str(tmp_path) not in str(refused.value)
def test_a_missing_file_raises_the_given_error(tmp_path):
    with pytest.raises(MappingError, match=r"absent\.ttl"):
        turtle.read([tmp_path / "absent.ttl"], MappingError)
```

- [ ] Step 3: write `tests/domain/test_records.py`, failing: `DATA_TABLES` has 14 pairs and
  starts with `("cooperative", "cooperatives")`; `record_type("sales_order") is SalesOrder`;
  `record_type("concept")` raises `KeyError`; `rows(dataset, "lot") is dataset.lots`.
- [ ] Step 4: move the `taxonomy` and `dataset` session fixtures from `tests/seed/conftest.py`
  to `tests/conftest.py`, so tests outside `tests/seed/` can use them.
- [ ] Step 5: implement. `turtle.read` takes the three `except` branches and the message
  that `load_taxonomy` has today, and turns an `OSError` into `error(f"{file.name}: {reason}")`
  with the system's short reason. `load_taxonomy` keeps its "no Turtle files" check.
  `seed/load.py` imports `DATA_TABLES` from `domain.records` and takes its column names from
  `record_type`, and `tests/seed/test_load.py` line 35 follows.
- [ ] Step 6: run `uv run pytest tests/rdf tests/domain tests/seed -n auto -q`. Expected: all
  pass, the pinned digest among them.
- [ ] Step 7: run `scripts/check.sh` and commit: "Add pyshacl and pyyaml, one Turtle reader
  and the table list in the domain package."

### Task 2: the ontology file, its value and its loader

Files:
- Create: `ontology/ontology.ttl`, `src/semantic_lab/domain/ontology.py`,
  `src/semantic_lab/rdf/ontology.py`, `tests/domain/test_ontology.py`,
  `tests/rdf/test_ontology.py`

Interfaces consumed: `turtle.read`, `OntologyError`.

Interfaces produced:

```python
# domain/ontology.py
NAMESPACE = "https://semantic-lab.example/ontology#"
CONCEPT = "http://www.w3.org/2004/02/skos/core#Concept"
XSD_TYPES: tuple[str, ...]            # the full IRIs of xsd:string, integer, decimal and date

@dataclass(frozen=True)
class OntologyClass:
    iri: str
    parent: str | None

@dataclass(frozen=True)
class Property:
    iri: str
    kind: Literal["object", "datatype"]
    domain: str | None
    range: str

@dataclass(frozen=True)
class Ontology:
    classes: tuple[OntologyClass, ...]        # sorted by IRI
    properties: tuple[Property, ...]          # sorted by IRI
    def class_of(self, iri: str) -> OntologyClass     # OntologyError when unknown
    def property_of(self, iri: str) -> Property       # OntologyError when unknown

def build_ontology(classes: Iterable[OntologyClass], properties: Iterable[Property]) -> Ontology

# rdf/ontology.py
def ontology_graph(file: Path) -> Graph               # raises OntologyError
def ontology_of(graph: Graph) -> Ontology             # raises OntologyError
```

`build_ontology` refuses, each with an `OntologyError` that names the term: an IRI used
twice; an IRI outside `NAMESPACE`; a parent that is no class; a subclass cycle; an object
property with no domain or with a domain that is no class; an object property whose range is
neither a class nor `CONCEPT`; a datatype property whose range is not in `XSD_TYPES`, or whose
domain is stated and is no class. `ontology_of` reads the nodes typed `owl:Class`,
`owl:ObjectProperty` and `owl:DatatypeProperty` and refuses a term with two
`rdfs:subClassOf`, two `rdfs:domain`, or a number of `rdfs:range` other than one.

- [ ] Step 1: write `tests/domain/test_ontology.py`, failing: one parametrised test over the
  eight refusals above, each matching the offending IRI, and one test that a valid pair of
  inputs comes back sorted by IRI.
- [ ] Step 2: write `tests/rdf/test_ontology.py`, failing. On small inline Turtle: the three
  refusals of `ontology_of`. On the repository's file:

```python
def test_the_file_holds_14_classes_and_50_properties(ontology):
    assert len(ontology.classes) == 14
    assert Counter(p.kind for p in ontology.properties) == {"object": 18, "datatype": 32}
def test_the_two_subclasses(ontology):
    parents = {c.iri: c.parent for c in ontology.classes if c.parent}
    assert parents == {SL + "Blend": SL + "Product", SL + "SingleLotProduct": SL + "Product"}
def test_only_code_and_name_have_no_domain(ontology):
    assert {p.iri for p in ontology.properties if p.domain is None} == {SL + "code", SL + "name"}
def test_pinned_terms(ontology):
    share = ontology.property_of(SL + "share")
    assert (share.kind, share.domain, share.range) == ("datatype", SL + "BatchComponent", XSD + "decimal")
    region = ontology.property_of(SL + "inRegion")
    assert (region.domain, region.range) == (SL + "Cooperative", CONCEPT)
```

- [ ] Step 3: run both files. Expected: they fail on the missing modules.
- [ ] Step 4: implement the two modules and write `ontology/ontology.ttl` from the tables in
  "The ontology's terms", with the labels and comments that section asks for.
- [ ] Step 5: run both files. Expected: pass.
- [ ] Step 6: run `scripts/check.sh` and commit: "Add the ontology of the Cumbre Coffee
  domain, with its value type and its loader."

### Task 3: SHACL validation, and the shapes for the taxonomies and the ontology

Files:
- Create: `ontology/shapes.ttl`, `src/semantic_lab/rdf/shacl.py`, `tests/rdf/test_shacl.py`,
  `tests/guards/test_shapes.py`

Interfaces consumed: `turtle.read`, `taxonomy_graph`, `ontology_graph`, `OntologyError`.

Interfaces produced:

```python
# rdf/shacl.py
@dataclass(frozen=True)
class Violation:
    focus: str                # the focus node, an IRI as text
    constraint: str           # local name of sh:sourceConstraintComponent, e.g. "MinCountConstraintComponent"
    path: str | None          # sh:resultPath when it is an IRI, else None
    value: str | None
    message: str              # on one line
    def line(self) -> str     # "<focus> <constraint>[ <path>]: <message>"

def shapes_graph(file: Path) -> Graph                 # raises OntologyError
def validate(data: Graph, shapes: Graph, ontology: Graph | None = None) -> tuple[Violation, ...]
```

`validate` calls `pyshacl.validate(data, shacl_graph=shapes, ont_graph=ontology,
inference="none")`, reads the report graph and returns the violations sorted by focus,
constraint, path and message. A `pyshacl.errors.ReportableRuntimeError` becomes an
`OntologyError` that starts with `shapes:` and fits on one line.

- [ ] Step 1: write `tests/rdf/test_shacl.py` on small inline graphs, failing: a conforming
  graph gives `()`; one missing value gives one `Violation` with the pinned `focus`,
  `constraint == "MinCountConstraintComponent"` and `path`; two violations come back in
  sorted order whatever order the triples were added in; a shape with `sh:minCount "many"`
  raises `OntologyError` matching `^shapes:`; a node typed only with a subclass is reported
  by its parent's shape when the ontology graph is passed, and is not when it is left out;
  `data` holds the same triples after the call as before.
- [ ] Step 2: write `tests/guards/test_shapes.py`, failing. Two tests assert
  `validate(taxonomy_graph(TAXONOMY_DIR), shapes) == ()` and the same for the ontology graph.
  Two fault tables follow, each a parametrised test that parses a small faulty Turtle text,
  validates it and asserts that one violation has the expected focus and constraint:

| Group | Fault | Constraint |
|---|---|---|
| taxonomy | a node with `skos:inScheme` and no type | `ClassConstraintComponent` |
| taxonomy | notation `t.a` on the IRI `.../taxonomy/t#b` | `SPARQLConstraintComponent` |
| taxonomy | two English `skos:prefLabel` | `UniqueLangConstraintComponent` |
| taxonomy | a `skos:prefLabel` in French | `LanguageInConstraintComponent` |
| taxonomy | a concept in two schemes | `MaxCountConstraintComponent` |
| taxonomy | no `skos:notation` | `MinCountConstraintComponent` |
| ontology | a class with no Spanish label | `MinCountConstraintComponent` |
| ontology | a class with no comment | `MinCountConstraintComponent` |
| ontology | an object property with two domains | `MaxCountConstraintComponent` |
| ontology | an object property whose range is `xsd:string` | `OrConstraintComponent` |
| ontology | a datatype property whose range is `xsd:float` | `InConstraintComponent` |

- [ ] Step 3: run both files. Expected: they fail on the missing module and file.
- [ ] Step 4: implement `rdf/shacl.py` and write the taxonomy and ontology groups of
  `ontology/shapes.ttl` from "The shapes".
- [ ] Step 5: run both files. Expected: pass. If the repository's taxonomies or ontology
  break a shape, the file is wrong or the shape is: read the violation and fix the one that
  disagrees with this plan.
- [ ] Step 6: run `scripts/check.sh` and commit: "Validate the taxonomies and the ontology
  against SHACL shapes."

### Task 4: the mapping file, its value, its reader and its check

Files:
- Create: `ontology/mapping.yaml`, `src/semantic_lab/domain/mapping.py`,
  `src/semantic_lab/rdf/mapping.py`, `tests/domain/test_mapping.py`,
  `tests/rdf/test_mapping.py`, `tests/rdf/test_mapping_db.py`

Interfaces consumed: `Ontology`, `Taxonomy`, `DATA_TABLES`, `record_type`, `MappingError`.

Interfaces produced:

```python
# domain/mapping.py
@dataclass(frozen=True)
class Condition:
    column: str
    under: tuple[str, ...]                    # concept keys

@dataclass(frozen=True)
class ClassEntry:
    iri: str
    table: str
    key: tuple[str, ...]
    when: Condition | None

@dataclass(frozen=True)
class Link:
    table: str
    source: str                               # `from` in the file
    target: str                               # `to` in the file

@dataclass(frozen=True)
class PropertyEntry:
    iri: str
    columns: tuple[tuple[str, str], ...]      # (table, column); empty when `link` is set
    link: Link | None

@dataclass(frozen=True)
class Mapping:
    classes: tuple[ClassEntry, ...]           # sorted by IRI
    properties: tuple[PropertyEntry, ...]     # sorted by IRI
    def postgres_columns(self) -> frozenset[tuple[str, str]]   # every (table, column) named anywhere

def problems(mapping: Mapping, ontology: Ontology, taxonomy: Taxonomy) -> tuple[str, ...]

# rdf/mapping.py
def load_mapping(file: Path) -> Mapping       # raises MappingError
```

`load_mapping` refuses, each with a one-line `MappingError` that starts with the file's name:
text that is not YAML; a top level that is not a mapping with exactly the keys `classes` and
`properties`; a term that does not start with `sl:`; an entry without `postgres`; a key it
does not know, at any level, named in the message; a `key` that is not a non-empty list of
strings; a column not of the form `table.column`; a property with both `columns` and `link`,
or with neither.

`problems` returns one sorted line per fault and `()` when there is none:
1. An ontology class or property with no entry, and an entry whose term the ontology does not
   hold or holds as the other kind.
2. A class entry whose table is no data table, whose key or `when` column is not a field of
   that table's record, or whose `under` key the taxonomy does not hold.
3. Two unconditional class entries on one table. A conditional entry whose class has no
   parent in the ontology, or whose parent's entry is not the unconditional entry of the same
   table with the same key.
4. A property column whose table has no unconditional class entry, or that is not a field of
   the table's record. A link whose table has a class entry or is no data table, or whose
   `from` or `to` is not a field. A link on a datatype property.
5. A column of a data table that no property maps, and one that two map. A data table that is
   neither a class's table nor a link's.

- [ ] Step 1: write `tests/domain/test_mapping.py`, failing: a small hand-built ontology,
  taxonomy and mapping over the real tables `farm` and `cooperative` give `()`, and one
  parametrised case per numbered fault above gives a line that names the term or the column.
  `postgres_columns` returns the key, `when`, property and link columns together.
- [ ] Step 2: write `tests/rdf/test_mapping.py`, failing: one parametrised case per refusal
  of `load_mapping`, each matching the file's name and fitting one line. On the repository's
  files:

```python
def test_the_file_maps_every_term_and_every_column(mapping, ontology, taxonomy):
    assert problems(mapping, ontology, taxonomy) == ()
    assert (len(mapping.classes), len(mapping.properties)) == (14, 50)
    assert len(mapping.postgres_columns()) == 63
def test_the_two_conditional_classes(mapping):
    conditions = {c.iri: c.when for c in mapping.classes if c.when}
    assert conditions == {
        SL + "Blend": Condition("category_key", ("category.blend",)),
        SL + "SingleLotProduct": Condition("category_key", ("category.decaf", "category.single-origin")),
    }
```

- [ ] Step 3: write `tests/rdf/test_mapping_db.py`, marked `db`, failing: with the `seeded`
  fixture, every pair in `postgres_columns()` is a row of
  `select table_name, column_name from information_schema.columns where table_schema = 'public'`.
- [ ] Step 4: run the two offline files. Expected: they fail on the missing modules.
- [ ] Step 5: implement the two modules and write `ontology/mapping.yaml` from the tables in
  "The ontology's terms". `Condition.under` is stored sorted.
- [ ] Step 6: run the two offline files, then `uv run pytest -m db tests/rdf -q`. Expected:
  pass.
- [ ] Step 7: run `scripts/check.sh` and commit: "Map every ontology term to its Postgres
  table or column and check the two against each other."

### Task 5: a sample of the dataset and its export as RDF

Files:
- Create: `src/semantic_lab/domain/sample.py`, `src/semantic_lab/rdf/export.py`,
  `tests/domain/test_sample.py`, `tests/rdf/test_export.py`

Interfaces consumed: `Dataset`, `rows`, `record_type`, `Taxonomy`, `Ontology`, `Mapping`,
`MappingError`.

Interfaces produced:

```python
# domain/sample.py
def first_orders(dataset: Dataset, count: int) -> Dataset

# rdf/export.py
DATA = "https://semantic-lab.example/data/"
def export(dataset: Dataset, taxonomy: Taxonomy, ontology: Ontology, mapping: Mapping) -> Graph
```

`first_orders` keeps the first `count` orders, their order lines, the roast batches those
lines name and the components of those batches. Every other table stays whole. A negative
count raises `ValueError`, and a count at or above the number of orders returns a dataset
equal to the one given. The result is closed: nothing in it names a row that was cut.

`export` follows "The exported RDF". It raises `MappingError` when it cannot build a node:
an object property whose range class, or a link whose domain class, has a key of more than one
column. A concept key the taxonomy does not hold raises the taxonomy's own `TaxonomyError`.

- [ ] Step 1: write `tests/domain/test_sample.py`, failing: for `first_orders(dataset, 20)`,
  20 orders; every line's order is among them; the batch codes equal the ones the lines name;
  every component's batch is kept; `lots`, `customers` and `products` are the same objects as
  in the input; the two edge cases above.
- [ ] Step 2: write `tests/rdf/test_export.py`, failing, on
  `export(first_orders(dataset, 20), ...)` with the repository's files:

```python
def test_a_lot_becomes_a_typed_node_with_typed_values(graph, sample, taxonomy):
    lot = sample.lots[0]
    node = URIRef(f"{DATA}lot/{lot.code}")
    assert (node, RDF.type, SL.Lot) in graph
    assert graph.value(node, SL.producedBy) == URIRef(f"{DATA}cooperative/{lot.cooperative_code}")
    assert graph.value(node, SL.weightKg) == Literal(lot.weight_kg, datatype=XSD.decimal)
    assert graph.value(node, SL.harvestedOn) == Literal(lot.harvested_on, datatype=XSD.date)
    assert graph.value(node, SL.process) == URIRef(taxonomy.get(lot.process_key).iri)
def test_link_tables_become_one_triple_per_row(graph, sample):
    assert len(list(graph.subject_objects(SL.harvestedFrom))) == len(sample.lot_farms)
    assert len(list(graph.subject_objects(SL.flavourNote))) == len(sample.product_flavours)
def test_a_composite_key_gives_a_path(graph, sample):
    line = sample.order_lines[0]
    assert (URIRef(f"{DATA}order-line/{line.order_code}/{line.line_no}"), RDF.type, SL.OrderLine) in graph
def test_a_blend_is_typed_twice_and_has_no_origin_region(graph, sample): ...
def test_a_one_lot_product_is_a_single_lot_product_with_a_region(graph, sample): ...
def test_a_null_gives_no_triple(graph, sample):
    for row in sample.certifications:
        node = URIRef(f"{DATA}certification/{row.cooperative_code}/{row.certification}/{row.valid_from}")
        assert ((node, SL.validUntil, None) in graph) == (row.valid_until is not None)
    assert all(str(o) != "None" for o in graph.objects() if isinstance(o, Literal))
def test_each_class_table_gives_one_node_per_row(graph, sample):
    assert len(set(graph.subjects(RDF.type, SL.OrderLine))) == len(sample.order_lines)
def test_two_exports_hold_the_same_triples(sample, ...): ...
def test_a_reference_to_a_class_with_a_two_column_key_is_refused(...): ...   # MappingError
```

- [ ] Step 3: run both files. Expected: they fail on the missing modules.
- [ ] Step 4: implement the two modules.
- [ ] Step 5: run both files. Expected: pass.
- [ ] Step 6: run `scripts/check.sh` and commit: "Export the generator's rows as RDF through
  the mapping."

### Task 6: the data shapes

Files:
- Modify: `ontology/shapes.ttl`, `tests/guards/test_shapes.py`

Interfaces consumed: `validate`, `export`, `first_orders`, `taxonomy_graph`, `ontology_graph`,
`shapes_graph`, the `dataset` fixture.

- [ ] Step 1: add to `tests/guards/test_shapes.py`, failing. The data graph of a sample is its
  export plus the taxonomy graph, and every validation passes the ontology graph.

```python
def test_the_first_200_orders_conform(...):
    assert validate(data_graph(first_orders(dataset, 200)), shapes, ontology_graph_) == ()
def test_every_class_with_a_table_has_a_closed_shape(shapes, mapping):
    # for each unconditional class entry: one sh:NodeShape with sh:targetClass <class> and sh:closed true
```

  Then one parametrised test over the faults below. Each case copies the data graph of
  `first_orders(dataset, 20)`, changes it and asserts a violation with the named constraint
  whose focus is the changed node (for a SPARQL rule, the batch).

| Fault | Constraint |
|---|---|
| a lot's `weightKg` set to -1 | `MinExclusiveConstraintComponent` |
| a shipment's `arrivedOn` set before its `departedOn` | `LessThanConstraintComponent` |
| a certification's `standard` set to `bio` | `InConstraintComponent` |
| a customer's `code` set to `X1` | `PatternConstraintComponent` |
| a farm's `altitudeMetres` written as a string | `DatatypeConstraintComponent` |
| a customer given `sl:colour` | `ClosedConstraintComponent` |
| an order line's `lineOf` pointed at a node that does not exist | `ClassConstraintComponent` |
| a lot with a second `producedBy` | `MaxCountConstraintComponent` |
| a blend given an `originRegion` | `MaxCountConstraintComponent` |
| a single-lot product stripped of its `originRegion` | `MinCountConstraintComponent` |
| a product stripped of its `sl:Blend` type | `XoneConstraintComponent` |
| a cooperative's `inRegion` pointed at a country | `NodeConstraintComponent` |
| a lot's `process` pointed at a flavour concept | `NodeConstraintComponent` |
| a lot's `harvestedFrom` pointed at a farm of another cooperative | `EqualsConstraintComponent` |
| an order line's `fromBatch` pointed at a batch of another product | `EqualsConstraintComponent` |
| one component's `share` raised by 0.01 | `SPARQLConstraintComponent` |
| a batch's `outputKg` set to 0.01 | `SPARQLConstraintComponent` |
| a single-lot batch given a second component | `SPARQLConstraintComponent` |
| a single-lot batch's `fromLot` pointed at a lot of another region | `SPARQLConstraintComponent` |

- [ ] Step 2: run the file. Expected: the new tests fail, the ones from Task 3 pass.
- [ ] Step 3: write the data group of `ontology/shapes.ttl` from "The shapes".
- [ ] Step 4: run the file. Expected: pass, in under 30 seconds. A violation on the unchanged
  sample means the shape, the export or the mapping disagrees with this plan: fix that one,
  never the test.
- [ ] Step 5: run `scripts/check.sh` and commit: "Add the SHACL shapes of the domain's data
  and prove each rule on a faulty example."

### Task 7: the command, the documents and the pull request

Files:
- Create: `src/semantic_lab/commands/ontology.py`, `tests/commands/test_ontology.py`
- Modify: `AGENTS.md`, `CODING_STANDARDS.md`, `README.md`,
  `docs/superpowers/specs/2026-11-16-semantic-lab-design.md`,
  `docs/superpowers/specs/measured-facts.md`

Interface produced:

```python
# commands/ontology.py
def main(argv: Sequence[str], out: TextIO, err: TextIO) -> int
```

`python -m semantic_lab.commands.ontology` takes `--ontology-dir` (default `ontology`),
`--seed` (default `DEFAULT_SEED`), `--orders` (default 200) and `--full`, which exports every
order. It reads no setting and opens no connection. It runs four checks and prints one line
each: `ok` or `FAIL`, the check's name and what it covered.

```text
ok    taxonomy shapes   442 triples
ok    ontology shapes   <n> triples
ok    mapping           14 classes, 50 properties, 63 columns
ok    data shapes       <n> triples from the first 200 orders
```

A `FAIL` line is followed by the check's problems, indented, at most 20, then `and <n> more`.
A failed mapping check does not stop the data check: a `MappingError` from the export is that
check's one problem. The command exits 0 when all four are `ok` and 1 otherwise. A file it
cannot read or parse (`TaxonomyError`, `OntologyError`, `MappingError`) and a
`GenerationError` print one line on stderr that starts with `ontology:` and exit 1.

- [ ] Step 1: write `tests/commands/test_ontology.py`, failing: on the repository's folder,
  exit 0 and four lines that start with `ok`; two runs print the same text; on a copy of the
  folder in `tmp_path` whose `mapping.yaml` has lost the `sl:share` entry, exit 1, a
  `FAIL  mapping` line and a problem line that names `sl:share` or `roast_batch_lot.share`;
  on a copy whose `shapes.ttl` is cut in half, exit 1, one line on stderr that starts with
  `ontology:` and no traceback; with `--ontology-dir` pointing at a folder that does not
  exist, the same.
- [ ] Step 2: run it. Expected: it fails on the missing module.
- [ ] Step 3: implement the command, with the entry-point block the other commands have.
- [ ] Step 4: run the file, then `uv run python -m semantic_lab.commands.ontology` and
  `time uv run python -m semantic_lab.commands.ontology --full`. Expected: four `ok` lines
  each time. Note both wall times and the two triple counts.
- [ ] Step 5: update the documents.
  - `AGENTS.md`: the command under Commands, marked `[read-only]`; the Architecture tree
    (the new `domain/` and `rdf/` modules, `commands/ontology.py`, the three files in
    `ontology/`); unit 3 in the opening paragraph.
  - `CODING_STANDARDS.md`: `pyshacl` and `pyyaml` in the runtime dependencies; `rdf/`'s row
    in the import table now says it also exports and validates; `domain/records.py` leaves
    the list of modules that need no mirror test, since it now has two functions and a test
    file.
  - `README.md`: units 1 to 3 are built, and one paragraph on the three files and the command.
  - The design: the Architecture tree's `domain/` line; check 2 of the three checks, which
    in this unit covers the ontology against the mapping, every column mapped once and the
    Postgres targets, while units 4 and 5 add the Neo4j and Cube targets with their checks;
    check 3, which validates the first 200 orders offline and every row with `--full`;
    items 3, 4 and 5 of "Order of work" to match; and two sentences in "The domain": regions
    are concepts and have no class, and `BatchComponent` exists because RDF has no properties
    on a relation.
  - `measured-facts.md`: a section "The ontology (unit 3)" with the facts of "Measured before
    planning" that still hold, the two wall times and triple counts from Step 4, and the
    pinned `pyshacl` and `pyyaml` versions from `uv.lock`.
- [ ] Step 6: run the ladder's last rung: `uv run pytest -n auto -m "not db and not model"`,
  then `uv run pytest -m db`. Expected: all pass.
- [ ] Step 7: run `scripts/check.sh` and commit: "Add the ontology command and bring the
  documents up to unit 3."
- [ ] Step 8: push the branch and open the pull request against `main` with a body in the
  form of pull request 2 (Summary, Evidence, Merge danger). The owner merges.

## Self-review

- Coverage of the design. Check 1 is Task 3. Check 2 is Task 4 for the part this unit can
  build, and Task 7 writes down what units 4 and 5 add. Check 3 is Tasks 5 and 6. The two
  items unit 2 left for this unit, that every concept is typed and that its IRI matches its
  key, are `shape:TypedSkos` and the SPARQL rule of `shape:Concept`.
- The design's non-goal stands: no reasoner runs. Subclasses are used once, for the two kinds
  of product, and no subproperty is declared because the domain has none.
- Every name a later task uses is defined in an earlier task's interface block.
