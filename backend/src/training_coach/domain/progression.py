"""When to move up the ladder. Pure logic, no I/O.

Rule (product spec): an exercise is ready to progress when every planned set reached the top
of the range in each of the last two sessions at the current ladder step. The user confirms
the move; the new step starts again at the bottom of the range.
"""

from collections.abc import Iterable, Sequence
from enum import StrEnum

from training_coach.domain.enums import Side
from training_coach.domain.targets import Prescription

SESSIONS_REQUIRED = 2


class Progress(StrEnum):
    HOLD = "hold"
    READY = "ready"
    TOP_OF_LADDER = "top_of_ladder"  # rule met, but there is no harder variation yet


def session_met_top(item: Prescription, values: Sequence[int]) -> bool:
    return len(values) >= item.sets and all(v >= item.rep_max for v in values[: item.sets])


def assess(
    item: Prescription,
    recent: Sequence[Sequence[int]],
    has_next_step: bool,
) -> Progress:
    """``recent`` holds the per-set values of recent sessions at this step, newest first."""
    latest = recent[:SESSIONS_REQUIRED]
    if len(latest) < SESSIONS_REQUIRED or not all(session_met_top(item, s) for s in latest):
        return Progress.HOLD
    return Progress.READY if has_next_step else Progress.TOP_OF_LADDER


def combine_sides(sets: Iterable[tuple[int, Side, int]], *, unilateral: bool) -> list[int]:
    """Per-set values for one session, from ``(set_no, side, value)`` rows, in set order.

    The list always runs from set 1 to the highest logged set, so a gap cannot shift later
    sets into its place: a missing set counts as 0. For unilateral work a set needs both
    sides and the weaker side counts; a set with one side missing counts as 0.
    """
    by_set: dict[int, dict[Side, int]] = {}
    for set_no, side, value in sets:
        if set_no < 1:
            raise ValueError(f"set numbers start at 1, got {set_no}")
        by_set.setdefault(set_no, {})[side] = value

    def value_of(sides: dict[Side, int]) -> int:
        if unilateral:
            if Side.LEFT not in sides or Side.RIGHT not in sides:
                return 0
            return min(sides[Side.LEFT], sides[Side.RIGHT])
        return min(sides.values())

    last = max(by_set, default=0)
    return [value_of(by_set[n]) if n in by_set else 0 for n in range(1, last + 1)]
