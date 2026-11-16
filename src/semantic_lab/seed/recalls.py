"""Placing the recalls: which customers received coffee from a recalled lot."""

import random
from collections import defaultdict

from semantic_lab.domain.errors import GenerationError
from semantic_lab.seed import planted
from semantic_lab.seed.batches import Batches, recalled_batches
from semantic_lab.seed.orders import Draft, Drafted

RECALL_CUSTOMERS = (12, 30)


def reach_recalled(drafted: Drafted, batches: Batches, rng: random.Random) -> None:
    """Redirect lines to the batches of each recalled lot, one line for each customer reached.

    A line is chosen only when its product is the batch's product and it was ordered after the
    batch was roasted and no later than the recall. The loop visits the lot's batches in turn and
    gives each at most one new customer per pass, so a lot's batches share the target between
    them and a batch may get none. No customer is counted twice for a lot, so the number of
    customers a lot reaches is the target drawn here. A seed with too few matching orders raises
    `GenerationError`.
    """
    by_code = {b.code: b for b in batches.roast_batches}
    lines_of_product: dict[str, list[Draft]] = defaultdict(list)
    for line in drafted.lines:
        lines_of_product[line.product_code].append(line)
    for lot, codes in recalled_batches(batches).items():
        recall_day = planted.RECALL_DATES[lot]
        target = rng.randint(*RECALL_CUSTOMERS)
        reached: set[str] = set()
        while len(reached) < target:
            progressed = False
            for batch in (by_code[code] for code in codes):
                if len(reached) == target:
                    break
                candidates = [
                    line
                    for line in lines_of_product[batch.product_code]
                    if not line.pinned
                    and batch.roasted_on <= line.ordered_on <= recall_day
                    and line.customer_code not in reached
                ]
                if candidates:
                    line = rng.choice(candidates)
                    line.batch_code = batch.code
                    line.pinned = True
                    reached.add(line.customer_code)
                    progressed = True
            if not progressed:
                raise GenerationError(f"too few orders to reach {target} customers for lot {lot}")
