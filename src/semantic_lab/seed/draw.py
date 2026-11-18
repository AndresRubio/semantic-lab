"""Small draws shared by the generator modules."""

import random
from datetime import date, timedelta
from decimal import Decimal

from semantic_lab.domain.errors import GenerationError


def random_date(rng: random.Random, first: date, last: date) -> date:
    """A day from `first` to `last`, both ends included."""
    if first > last:
        raise GenerationError(f"no day to draw: {first} is after {last}")
    return first + timedelta(days=rng.randint(0, (last - first).days))


def decimal_from_hundredths(hundredths: int) -> Decimal:
    return (Decimal(hundredths) / 100).quantize(Decimal("0.01"))
