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
    load_kg: float | None = None  # its weight, on a loaded step (ADR-0072); one for both sides


@dataclass(frozen=True)
class LoggedExercise:
    exercise_id: int
    step_id: int
    sets: tuple[LoggedSet, ...]


Row = tuple[int, int, int, str, int, float | None]


def group(rows: Iterable[Row]) -> tuple[LoggedExercise, ...]:
    """``(exercise_id, step_id, set_no, side, value, load_kg)`` rows, as stored, into exercises:
    first seen first, each set once. A side logged on its own (one side done) shows on the
    left."""
    found: dict[tuple[int, int], dict[int, dict[str, int]]] = {}
    loads: dict[tuple[int, int, int], float] = {}
    for exercise_id, step_id, set_no, side, value, kg in rows:
        found.setdefault((exercise_id, step_id), {}).setdefault(set_no, {})[side] = value
        if kg is not None:
            loads[exercise_id, step_id, set_no] = kg
    return tuple(
        LoggedExercise(
            exercise_id,
            step_id,
            tuple(
                _set(number, sides[number], loads.get((exercise_id, step_id, number)))
                for number in sorted(sides)
            ),
        )
        for (exercise_id, step_id), sides in found.items()
    )


def _set(number: int, sides: dict[str, int], kg: float | None) -> LoggedSet:
    if Side.BOTH in sides:
        return LoggedSet(number, sides[Side.BOTH], load_kg=kg)
    left, right = sides.get(Side.LEFT), sides.get(Side.RIGHT)
    if left is None:
        return LoggedSet(number, right or 0, None, kg)
    return LoggedSet(number, left, right, kg)
