"""Last set: as many good reps as you can (ADR-0084). Pure logic, no I/O.

A per-person option, off by default. It applies only to exercises the catalogue marks
``failure_ok`` that count in reps, and only to the last set the day plans of each, after a
shorter day's trim. The set shows its usual target as a floor. It stays locked while a person
is new: until 8 weeks after their first logged workout.
"""

from datetime import date, timedelta

from training_coach.domain.enums import ExerciseKind

NEW_FOR = timedelta(weeks=8)


def available(first_workout: date | None, today: date) -> bool:
    """Whether the option can be on: 8 weeks after the first logged workout (``None``: none
    logged yet). ADR-0084 also locks it at level 3 or below (ADR-0083); once placement gives a
    person a level, that rule joins here as one more argument."""
    return first_workout is not None and today >= first_workout + NEW_FOR


def applies(kind: ExerciseKind, failure_ok: bool) -> bool:
    """Whether an exercise's last set can be as many good reps as you can."""
    return failure_ok and kind is ExerciseKind.REPS
