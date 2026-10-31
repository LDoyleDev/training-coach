"""When to move up the ladder. Pure logic, no I/O.

Rule (product spec): an exercise is ready to progress when every planned set reached the top
of the range in each of the last two sessions at the current ladder step. The user confirms
the move; the new step starts again at the bottom of the range.

A shorter day (ADR-0082) is judged on its own sets (ADR-0084): a session that says how many sets
it planned meets the top when each of those, the first ones, reached it. It counts toward the
two only if it planned at least two sets, or every set when the prescription plans fewer (a
one-set exercise could never move up otherwise); a day that doesn't count is passed over, so the
two are the last two that do. A session saved without its count (``None``) keeps the rule above:
every set the prescription plans, and it always counts.
"""

from collections.abc import Iterable, Sequence
from enum import StrEnum

from training_coach.domain.enums import Side
from training_coach.domain.targets import Prescription, planned_counts

SESSIONS_REQUIRED = 2
SETS_TO_COUNT = 2  # a day planning fewer sets of the exercise doesn't count (ADR-0084)


class Progress(StrEnum):
    HOLD = "hold"
    READY = "ready"
    TOP_OF_LADDER = "top_of_ladder"  # rule met, but there is no harder variation yet


def session_met_top(item: Prescription, values: Sequence[int], planned: int | None = None) -> bool:
    """Every set the session ``planned`` (every set of the prescription when None) reached the
    top of the range; sets past them don't matter."""
    count = item.sets if planned is None else planned
    return len(values) >= count and all(v >= item.rep_max for v in values[:count])


def _counts(item: Prescription, planned: int | None) -> bool:
    return planned is None or planned >= min(SETS_TO_COUNT, item.sets)


def assess(
    item: Prescription,
    recent: Sequence[Sequence[int]],
    has_next_step: bool,
    planned: Sequence[int | None] | None = None,
) -> Progress:
    """``recent`` holds the per-set values of recent sessions at this step, newest first;
    ``planned``, in the same order, the sets each one planned (ADR-0084)."""
    sessions = zip(recent, planned_counts(recent, planned), strict=True)
    latest = [(s, count) for s, count in sessions if _counts(item, count)][:SESSIONS_REQUIRED]
    if len(latest) < SESSIONS_REQUIRED or not all(
        session_met_top(item, s, count) for s, count in latest
    ):
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
