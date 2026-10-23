"""What a day's log shows on Today (ADR-0068): a workout's set logs grouped per exercise and
step, in the order they were done, with a one-sided exercise's left and right on one line."""

from collections.abc import Iterable
from dataclasses import dataclass

from training_coach.domain.enums import Side


@dataclass(frozen=True)
class LoggedSet:
    set_no: int
    left: int  # the value, or the left side's
    right: int | None = None  # the right side's, for one-sided sets; None: not one-sided


@dataclass(frozen=True)
class LoggedExercise:
    exercise_id: int
    step_id: int
    sets: tuple[LoggedSet, ...]


def group(rows: Iterable[tuple[int, int, int, str, int]]) -> tuple[LoggedExercise, ...]:
    """``(exercise_id, step_id, set_no, side, value)`` rows, as stored, into exercises: first
    seen first, each set once. A side logged on its own (one side done) shows on the left."""
    found: dict[tuple[int, int], dict[int, dict[str, int]]] = {}
    for exercise_id, step_id, set_no, side, value in rows:
        found.setdefault((exercise_id, step_id), {}).setdefault(set_no, {})[side] = value
    return tuple(
        LoggedExercise(
            exercise_id,
            step_id,
            tuple(_set(number, sides[number]) for number in sorted(sides)),
        )
        for (exercise_id, step_id), sides in found.items()
    )


def _set(number: int, sides: dict[str, int]) -> LoggedSet:
    if Side.BOTH in sides:
        return LoggedSet(number, sides[Side.BOTH])
    left, right = sides.get(Side.LEFT), sides.get(Side.RIGHT)
    if left is None:
        return LoggedSet(number, right or 0, None)
    return LoggedSet(number, left, right)
