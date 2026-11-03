"""Last set: as many good reps as you can (ADR-0084): locked for a person's first 8 weeks, and
only on exercises the catalogue allows that count in reps."""

from datetime import date

import pytest

from training_coach.domain.enums import ExerciseKind
from training_coach.domain.last_set import applies, available

FIRST = date(2026, 9, 1)


@pytest.mark.parametrize(
    ("first", "today", "expected"),
    [
        pytest.param(None, date(2026, 10, 31), False, id="nothing-logged"),
        pytest.param(FIRST, FIRST, False, id="first-day"),
        pytest.param(FIRST, date(2026, 10, 26), False, id="a-day-short-of-8-weeks"),
        pytest.param(FIRST, date(2026, 10, 27), True, id="8-weeks"),
        pytest.param(FIRST, date(2027, 1, 1), True, id="later"),
    ],
)
def test_available_after_the_first_8_weeks(first: date | None, today: date, expected: bool) -> None:
    assert available(first, today) is expected


@pytest.mark.parametrize(
    ("kind", "failure_ok", "expected"),
    [
        pytest.param(ExerciseKind.REPS, True, True, id="reps-failure-ok"),
        pytest.param(ExerciseKind.REPS, False, False, id="reps-not-failure-ok"),
        pytest.param(ExerciseKind.SECONDS, True, False, id="seconds"),
        pytest.param(ExerciseKind.DURATION_MIN, True, False, id="minutes"),
    ],
)
def test_applies_only_to_failure_ok_reps(
    kind: ExerciseKind, failure_ok: bool, expected: bool
) -> None:
    assert applies(kind, failure_ok) is expected
