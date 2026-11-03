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

Stepping down is suggested, never done for the person (ADR-0084): ``step_down`` offers the step
below when the last two sessions at the step, not counting the first there (its baseline), each
had most of the sets it planned short of their targets and below the bottom of the range.
After three weeks or more without an exercise, ``returning`` says to offer one step down for the
day of the return.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from training_coach.domain.enums import Side
from training_coach.domain.targets import Pace, Prescription, judged, planned_counts

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


class StepDown(StrEnum):
    """Whether to suggest the step below (ADR-0084). The person decides."""

    NONE = "none"
    SUGGEST = "suggest"  # the step below
    FIRST_STEP = "first_step"  # the rule is met with no step below: an easier exercise instead


def out_of_reach(item: Prescription, given: Sequence[int], done: Sequence[int]) -> bool:
    """Most of the sets a session planned fell short of their targets and of the bottom of the
    range. ``given`` and ``done`` hold one value per set planned (``targets.judged``)."""
    short = sum(1 for g, v in zip(given, done, strict=True) if v < g and v < item.rep_min)
    return short * 2 > len(done)


def judged_sessions(count: int, skipped: Sequence[bool] | None = None) -> list[int]:
    """The indexes of a newest-first history of ``count`` sessions that the step-down rule
    judges, newest first: not the oldest (the baseline, ADR-0027) and none ``skipped`` (a
    strength-block session, or a level chosen for today only)."""
    if skipped is not None and len(skipped) != count:
        raise ValueError(f"{len(skipped)} skip flags for {count} sessions")
    return [i for i in range(count - 1) if skipped is None or not skipped[i]]


def step_down(
    item: Prescription,
    recent: Sequence[Sequence[int]],
    *,
    has_step_below: bool,
    pace: Pace = Pace.STANDARD,
    planned: Sequence[int | None] | None = None,
    skipped: Sequence[bool] | None = None,
    loaded: bool = False,
    failure_sets: Sequence[int | None] | None = None,
) -> StepDown:
    """Suggest the step below when the last two sessions judged (``judged_sessions``) both had
    the bottom of the range out of reach (``out_of_reach``). ``recent`` is every session at the
    step, newest first, with the weaker side of a one-sided set (``combine_sides``); ``planned``
    the sets each planned and ``failure_sets`` each one's last set to failure (ADR-0084); ``pace``
    gives the targets they were given (ADR-0057). A loaded step never: the weight is what to
    lower (ADR-0072)."""
    if loaded:
        return StepDown.NONE
    sessions = judged(item, recent, pace, planned, failure_sets)
    latest = judged_sessions(len(recent), skipped)[:SESSIONS_REQUIRED]
    if len(latest) < SESSIONS_REQUIRED or not all(out_of_reach(item, *sessions[i]) for i in latest):
        return StepDown.NONE
    return StepDown.SUGGEST if has_step_below else StepDown.FIRST_STEP


@dataclass(frozen=True)
class Catalogued:
    """An exercise of the catalogue, for naming an easier one (ADR-0083)."""

    name: str
    primes: frozenset[str]  # the muscles it counts fully for
    level: int | None  # its first step's level, 1-6; None for a step without one


EASY_LEVELS = (1, 2)


def easier_exercises(primes: frozenset[str], catalogue: Iterable[Catalogued]) -> list[str]:
    """The catalogue's exercises starting at level 1 or 2 that share a prime mover with
    ``primes``, in catalogue order: a suggestion at a ladder's first step."""
    return [c.name for c in catalogue if c.level in EASY_LEVELS and c.primes & primes]


RETURN_DAYS = 21  # three weeks or more away: ease back in, one step down today (ADR-0084)


def returning(last_done: date | None, today: date) -> bool:
    """``RETURN_DAYS`` or more since the exercise was last done. Never done is a start, not a
    return."""
    return last_done is not None and (today - last_done).days >= RETURN_DAYS
