"""Recomputes each stored answer in plain Python from the in-memory dataset, without SQL.

The reference SQL and these functions are two derivations of the same definitions. When they
disagree, one of them misreads a definition, and the stored answer is not trusted until the
wrong one is fixed.
"""

from collections import defaultdict
from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from semantic_lab.domain.records import Dataset, OrderLine
from semantic_lab.domain.taxonomy import Taxonomy
from semantic_lab.evals import questions
from semantic_lab.evals.questions import Question
from semantic_lab.rdf.taxonomy import load_taxonomy
from semantic_lab.seed.generate import DEFAULT_SEED, generate

QUESTIONS = Path(__file__).resolve().parent.parent.parent / "questions"
CENT = Decimal("0.01")
GRAM = Decimal("0.001")

Rows = list[list[object]]


class Model:
    """The dataset indexed the way the definitions are worded."""

    def __init__(self, taxonomy: Taxonomy, dataset: Dataset) -> None:
        self.taxonomy = taxonomy
        self.dataset = dataset
        self.order_date = {o.code: o.ordered_on for o in dataset.orders}
        self.order_customer = {o.code: o.customer_code for o in dataset.orders}
        self.customers = {c.code: c for c in dataset.customers}
        self.region_of_coop = {c.code: c.region_key for c in dataset.cooperatives}
        self.lots = {lot.code: lot for lot in dataset.lots}
        self.cost = {b.code: b.cost_per_kg for b in dataset.roast_batches}
        self.shares: dict[str, list[tuple[str, Decimal]]] = defaultdict(list)
        for link in dataset.roast_batch_lots:
            self.shares[link.roast_batch_code].append((link.lot_code, link.share))
        self.notes: dict[str, set[str]] = defaultdict(set)
        for flavour in dataset.product_flavours:
            self.notes[flavour.product_code].add(flavour.flavour_key)

    def lines(self, start: date, end: date) -> list[OrderLine]:
        """The order lines of orders placed from start to end, both days included."""
        return [
            line
            for line in self.dataset.order_lines
            if start <= self.order_date[line.order_code] <= end
        ]

    def year(self, year: int) -> list[OrderLine]:
        return self.lines(date(year, 1, 1), date(year, 12, 31))

    def lot_region(self, lot_code: str) -> str:
        return self.region_of_coop[self.lots[lot_code].cooperative_code]

    def up(self, key: str, steps: int) -> str:
        for _ in range(steps):
            parent = self.taxonomy.get(key).parent_key
            assert parent is not None
            key = parent
        return key

    def self_and_below(self, key: str) -> set[str]:
        return {key} | {c.key for c in self.taxonomy.descendants(key)}

    def label(self, key: str) -> str:
        return self.taxonomy.get(key).label_en


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def weight(value: Decimal) -> Decimal:
    return value.quantize(GRAM, rounding=ROUND_HALF_UP)


def quarter_of(day: date) -> str:
    return f"{day.year}-Q{(day.month - 1) // 3 + 1}"


def quarter_revenue(model: Model, lines: list[OrderLine]) -> Rows:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for line in lines:
        totals[quarter_of(model.order_date[line.order_code])] += line.amount
    return [[name, money(total)] for name, total in totals.items()]


def attributed_revenue_by_ancestor(model: Model, lines: list[OrderLine], steps: int) -> Rows:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for line in lines:
        for lot_code, share in model.shares[line.roast_batch_code]:
            ancestor = model.up(model.lot_region(lot_code), steps)
            totals[model.label(ancestor)] += line.amount * share
    return [[name, money(total)] for name, total in totals.items()]


def has_note_under(model: Model, product_code: str, concept: str) -> bool:
    return bool(model.notes[product_code] & model.self_and_below(concept))


def metric_revenue_by_country_2025(model: Model) -> Rows:
    return attributed_revenue_by_ancestor(model, model.year(2025), steps=1)


def metric_revenue_by_quarter_2025(model: Model) -> Rows:
    return quarter_revenue(model, model.year(2025))


def metric_top_customers_kg_2025(model: Model) -> Rows:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for line in model.year(2025):
        totals[model.order_customer[line.order_code]] += line.kg
    ranked = sorted(
        ((model.customers[code].name, total) for code, total in totals.items()),
        key=lambda pair: (-pair[1], pair[0]),
    )
    return [[name, weight(total)] for name, total in ranked[:5]]


def metric_orders_by_segment_2024(model: Model) -> Rows:
    counts: dict[str, int] = defaultdict(int)
    for order in model.dataset.orders:
        if order.ordered_on.year == 2024:
            counts[model.customers[order.customer_code].segment] += 1
    return [[segment, count] for segment, count in counts.items()]


def metric_organic_lots_2025(model: Model) -> Rows:
    count = 0
    for lot in model.dataset.lots:
        if lot.harvested_on.year != 2025:
            continue
        for cert in model.dataset.certifications:
            if (
                cert.cooperative_code == lot.cooperative_code
                and cert.certification == "organic"
                and cert.valid_from <= lot.harvested_on
                and (cert.valid_until is None or lot.harvested_on <= cert.valid_until)
            ):
                count += 1
                break
    return [[count]]


def hierarchy_kg_fruity_2025(model: Model) -> Rows:
    total = Decimal(0)
    for line in model.year(2025):
        if has_note_under(model, line.product_code, "flavour.fruity"):
            total += line.kg
    return [[weight(total)]]


def hierarchy_revenue_by_continent_2025(model: Model) -> Rows:
    return attributed_revenue_by_ancestor(model, model.year(2025), steps=2)


def hierarchy_margin_by_process_2025(model: Model) -> Rows:
    groups = {
        key: model.self_and_below(key)
        for key in ("process.washed", "process.natural", "process.honey")
    }
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for line in model.year(2025):
        margin = line.amount - line.kg * model.cost[line.roast_batch_code]
        for lot_code, share in model.shares[line.roast_batch_code]:
            process = model.lots[lot_code].process_key
            for key, members in groups.items():
                if process in members:
                    totals[model.label(key)] += margin * share
    return [[name, money(total)] for name, total in totals.items()]


def metric_revenue_by_country_2024_q4(model: Model) -> Rows:
    lines = model.lines(date(2024, 10, 1), date(2024, 12, 31))
    return attributed_revenue_by_ancestor(model, lines, steps=1)


def metric_average_order_value_by_segment_2025(model: Model) -> Rows:
    order_value: dict[str, Decimal] = defaultdict(Decimal)
    for line in model.year(2025):
        order_value[line.order_code] += line.amount
    by_segment: dict[str, list[Decimal]] = defaultdict(list)
    for order_code, value in order_value.items():
        by_segment[model.customers[model.order_customer[order_code]].segment].append(value)
    return [
        [segment, money(sum(values, Decimal(0)) / len(values))]
        for segment, values in by_segment.items()
    ]


def hierarchy_kg_honey_process_2024(model: Model) -> Rows:
    honey = model.self_and_below("process.honey")
    total = Decimal(0)
    for line in model.year(2024):
        for lot_code, share in model.shares[line.roast_batch_code]:
            if model.lots[lot_code].process_key in honey:
                total += line.kg * share
    return [[weight(total)]]


def hierarchy_revenue_floral_by_quarter_2025(model: Model) -> Rows:
    lines = [
        line
        for line in model.year(2025)
        if has_note_under(model, line.product_code, "flavour.floral")
    ]
    return quarter_revenue(model, lines)


RECOMPUTE: dict[str, Callable[[Model], Rows]] = {
    "metric-revenue-by-country-2025": metric_revenue_by_country_2025,
    "metric-revenue-by-quarter-2025": metric_revenue_by_quarter_2025,
    "metric-top-customers-kg-2025": metric_top_customers_kg_2025,
    "metric-orders-by-segment-2024": metric_orders_by_segment_2024,
    "metric-organic-lots-2025": metric_organic_lots_2025,
    "hierarchy-kg-fruity-2025": hierarchy_kg_fruity_2025,
    "hierarchy-revenue-by-continent-2025": hierarchy_revenue_by_continent_2025,
    "hierarchy-margin-by-process-2025": hierarchy_margin_by_process_2025,
    "metric-revenue-by-country-2024-q4": metric_revenue_by_country_2024_q4,
    "metric-average-order-value-by-segment-2025": metric_average_order_value_by_segment_2025,
    "hierarchy-kg-honey-process-2024": hierarchy_kg_honey_process_2024,
    "hierarchy-revenue-floral-by-quarter-2025": hierarchy_revenue_floral_by_quarter_2025,
}


@pytest.fixture(scope="module")
def model() -> Model:
    taxonomy = load_taxonomy(QUESTIONS.parent / "ontology" / "taxonomy")
    return Model(taxonomy, generate(taxonomy, DEFAULT_SEED))


def every_question() -> tuple[Question, ...]:
    return questions.load(QUESTIONS / "dev.toml") + questions.load(QUESTIONS / "heldout.toml")


def as_stored(rows: Rows) -> list[list[object]]:
    """A recomputed row in the form the answer files hold: whole numbers as int, the rest of the
    Decimals as float."""
    return questions.to_json_rows(rows)


def test_every_question_has_a_recomputation() -> None:
    assert {q.id for q in every_question()} == set(RECOMPUTE)


@pytest.mark.parametrize("question", every_question(), ids=lambda q: q.id)
def test_the_stored_answer_is_what_plain_python_gets_from_the_dataset(
    model: Model, question: Question
) -> None:
    stored = questions.read_expected(QUESTIONS / "expected", question.id)
    recomputed = as_stored(RECOMPUTE[question.id](model))
    position = [question.columns.index(name) for name in question.key]

    def key_of(row: list[object]) -> tuple[object, ...]:
        return tuple(row[i] for i in position)

    assert len(recomputed) == len(stored), question.id
    if question.ordered:
        assert recomputed == stored
    else:
        assert sorted(recomputed, key=key_of) == sorted(stored, key=key_of)
