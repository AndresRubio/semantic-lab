import random
from datetime import date
from decimal import Decimal

import pytest

from semantic_lab.domain.errors import GenerationError
from semantic_lab.seed.draw import decimal_from_hundredths, random_date


def test_random_date_reaches_both_ends_and_stays_inside() -> None:
    first, last = date(2024, 3, 1), date(2024, 3, 4)
    rng = random.Random(1)
    days = {random_date(rng, first, last) for _ in range(200)}
    assert days == {date(2024, 3, day) for day in (1, 2, 3, 4)}


def test_random_date_of_one_day_is_that_day() -> None:
    day = date(2025, 12, 31)
    assert random_date(random.Random(3), day, day) == day


def test_random_date_refuses_a_first_day_after_the_last() -> None:
    with pytest.raises(GenerationError, match=r"2024-03-05.*2024-03-01"):
        random_date(random.Random(1), date(2024, 3, 5), date(2024, 3, 1))


@pytest.mark.parametrize(
    ("hundredths", "text"),
    [(0, "0.00"), (5, "0.05"), (100, "1.00"), (12345, "123.45"), (40000, "400.00")],
)
def test_decimal_from_hundredths_keeps_two_places(hundredths: int, text: str) -> None:
    value = decimal_from_hundredths(hundredths)
    assert value == Decimal(text)
    assert str(value) == text
    assert value.as_tuple().exponent == -2
