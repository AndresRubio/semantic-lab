"""The facts the generator plants on purpose, so the questions of later units have answers."""

from datetime import date

RECALLED_LOTS = ("L-0152", "L-0417")
RECALL_DATES = {"L-0152": date(2024, 9, 5), "L-0417": date(2025, 3, 18)}

LAPSED_COOPERATIVE = "C-07"
LAPSE_DATE = date(2025, 6, 30)

BLENDS = ("Alba", "Brisa")
SHARED_FARMS = 3
ALBA_POOL = tuple(f"L-{number:04d}" for number in range(1, 13))
BRISA_POOL = tuple(f"L-{number:04d}" for number in range(13, 25))
