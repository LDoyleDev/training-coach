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


def combine_sides(sets: Iterable[tuple[int, Side, int]]) -> list[int]:
    """Per-set values for one session, from ``(set_no, side, value)`` rows.

    For unilateral work the weaker side counts, so a set only "reaches the top" when both
    sides do. Missing set numbers are skipped; the result is in set order.
    """
    by_set: dict[int, int] = {}
    for set_no, _side, value in sets:
        by_set[set_no] = min(value, by_set.get(set_no, value))
    return [by_set[n] for n in sorted(by_set)]
