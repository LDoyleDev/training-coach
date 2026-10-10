"""Baseline tests and retests (2-A, #94, ADR-0037). Pure logic, no I/O.

A test day runs one day's tests from the product spec under recorded conditions. A test may be
skipped; what is done is checked here before anything is saved.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from training_coach.domain.enums import Side


class Unit(StrEnum):
    REPS = "reps"
    SECONDS = "seconds"
    METRES = "metres"  # the 12-minute run's distance
    CM = "cm"  # toe touch: past the toes is plus, short of them minus


class TimeOfDay(StrEnum):
    MORNING = "morning"
    MIDDAY = "midday"
    AFTERNOON = "afternoon"
    EVENING = "evening"


DAYS = (1, 2)

# What a result can be, per unit: wide enough for anyone, narrow enough to catch a typo.
RANGES = {
    Unit.REPS: (0, 500),
    Unit.SECONDS: (0, 3600),
    Unit.METRES: (0, 10_000),
    Unit.CM: (-60, 60),
}


@dataclass(frozen=True)
class FitnessTest:
    slug: str
    name: str
    day: int
    unit: Unit
    per_side: bool
    cue: str


@dataclass(frozen=True)
class Result:
    test: str  # slug
    side: Side  # BOTH, or LEFT and RIGHT for a one-sided test
    value: int


def problem(tests: Sequence[FitnessTest], day: int, results: Sequence[Result]) -> str | None:
    """Why ``results`` can't be saved as test day ``day``, or None when they can."""
    if day not in DAYS:
        return f"there is no test day {day}"
    if not results:
        return "nothing to save: every test was skipped"
    of_day = {t.slug: t for t in tests if t.day == day}
    seen: set[tuple[str, Side]] = set()
    for result in results:
        test = of_day.get(result.test)
        if test is None:
            return f"{result.test} isn't a day {day} test"
        sides = {Side.LEFT, Side.RIGHT} if test.per_side else {Side.BOTH}
        if result.side not in sides:
            return f"{test.name} is done {'per side' if test.per_side else 'once, not per side'}"
        if (result.test, result.side) in seen:
            return f"{test.name} is in twice"
        seen.add((result.test, result.side))
        low, high = RANGES[test.unit]
        if not low <= result.value <= high:
            return f"{test.name}: {result.value} {test.unit} is outside {low} to {high}"
    for slug, test in of_day.items():
        if test.per_side and len({s for t, s in seen if t == slug}) == 1:
            return f"{test.name} needs both sides, or skip it"
    return None
