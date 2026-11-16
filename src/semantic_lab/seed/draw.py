"""Small draws shared by the generator modules."""

import random
from datetime import date, timedelta
from decimal import Decimal


def random_date(rng: random.Random, first: date, last: date) -> date:
    return first + timedelta(days=rng.randint(0, (last - first).days))


def decimal_from_hundredths(hundredths: int) -> Decimal:
    return (Decimal(hundredths) / 100).quantize(Decimal("0.01"))
