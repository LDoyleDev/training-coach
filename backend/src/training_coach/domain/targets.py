"""Per-set targets for the next session of an exercise (ADR-0027). Pure logic, no I/O.

Rule: each set aims for what it did last time plus a step of about 10% of the top of the range
(halves round up, at least 1), never above the top. A set that missed the target it was given
keeps that target; after two misses in a row of the same target it aims one more than it did,
so a bad patch never leaves a target out of reach for good. With no history, aim for the bottom
of the range.

The targets each past session was given are replayed from the oldest session at this ladder
step, so nothing but the logged sets is needed. The first session there is the baseline and
never counts as a miss.

Example: last 8/7/6/5 in a 5-12 range, all targets met -> 9/8/7/6.

The person's pace (ADR-0057) changes only the step: steady is the smallest step of each kind,
fast at least twice that, standard the 10% rule above.

A shorter day (ADR-0082) is judged on its own sets (ADR-0084): each session can say how many
sets it planned, always the first ones. A set the day didn't plan isn't replayed, neither a miss
nor a 0. When it comes back it starts from the nearest set before it that day, as a load does
(ADR-0072): that set's next target, with no misses held against it. A set's baseline is the
first session at the step that planned it. A session saved without its count (``None``) planned
every set, so no past target moves.

A last set of as many good reps as you can (ADR-0084) counts as its target met when it reached
it: that set's next target is its target plus the step, not its reps plus the step, so one big
set doesn't set a target the next ordinary day can't reach. Below its target it is a miss, as
any set's would be. Other sets are judged as ever. Readiness and bests take the reps as done.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from training_coach.domain.enums import ExerciseKind

MISSES_BEFORE_EASING = 2


class Pace(StrEnum):
    """How big a step each set aims for (ADR-0057). A per-person setting."""

    STEADY = "steady"
    STANDARD = "standard"
    FAST = "fast"


# The step at a steady pace, and the least step at a fast pace, per kind (ADR-0057).
STEADY_STEP = {ExerciseKind.REPS: 1, ExerciseKind.SECONDS: 5, ExerciseKind.DURATION_MIN: 1}
FAST_STEP = {ExerciseKind.REPS: 2, ExerciseKind.SECONDS: 10, ExerciseKind.DURATION_MIN: 2}


@dataclass(frozen=True)
class Prescription:
    """What the plan asks for one exercise in a session."""

    sets: int
    rep_min: int
    rep_max: int
    kind: ExerciseKind = ExerciseKind.REPS

    def __post_init__(self) -> None:
        if self.sets < 1 or self.rep_min < 1 or self.rep_max < self.rep_min:
            raise ValueError(f"invalid prescription: {self}")


def step(item: Prescription, pace: Pace = Pace.STANDARD) -> int:
    """How much more each set aims for: about 10% of the top of the range at the standard
    pace; the smallest step at a steady pace; at least twice that at a fast pace."""
    if pace is Pace.STEADY:
        return STEADY_STEP[item.kind]
    standard = _standard_step(item)
    # Timed steps stay whole 5 s steps: both values already are.
    return max(FAST_STEP[item.kind], standard) if pace is Pace.FAST else standard


def _standard_step(item: Prescription) -> int:
    tenth = (item.rep_max + 5) // 10  # 10%, halves rounding up
    if item.kind is ExerciseKind.SECONDS:
        return max(5, (tenth + 2) // 5 * 5)  # whole 5 s steps
    if item.kind is ExerciseKind.DURATION_MIN:
        return 1
    return max(1, tenth)


def _cap(value: int, item: Prescription) -> int:
    return max(0, min(item.rep_max, value))


def planned_counts(
    history: Sequence[Sequence[int]], planned: Sequence[int | None] | None
) -> list[int | None]:
    """The sets each session in ``history`` planned, in the same order; ``None`` for a session
    saved without its count, and for every session when ``planned`` is None."""
    if planned is None:
        return [None] * len(history)
    if len(planned) != len(history):
        raise ValueError(f"{len(planned)} planned counts for {len(history)} sessions")
    if any(count is not None and count < 0 for count in planned):
        raise ValueError(f"a planned count is below 0: {planned}")
    return list(planned)


def failure_counts(
    history: Sequence[Sequence[int]], failure_sets: Sequence[int | None] | None
) -> list[int | None]:
    """The set each session in ``history`` ran to as many good reps as it could, numbered from
    1 as the log numbers them; ``None`` for a session without one, and for every session when
    ``failure_sets`` is None."""
    if failure_sets is None:
        return [None] * len(history)
    if len(failure_sets) != len(history):
        raise ValueError(f"{len(failure_sets)} failure sets for {len(history)} sessions")
    if any(n is not None and n < 1 for n in failure_sets):
        raise ValueError(f"set numbers start at 1: {failure_sets}")
    return list(failure_sets)


def _performed(item: Prescription, values: Sequence[int], planned: int | None) -> list[int]:
    """One value per set the session planned, at most the prescription's (all of them when
    ``planned`` is None). Missing sets start from the weakest logged set."""
    count = item.sets if planned is None else min(planned, item.sets)
    done = [_cap(v, item) for v in values[:count]]
    if not done:
        return [0] * count
    return done + [min(done)] * (count - len(done))


def targets(
    item: Prescription,
    history: Sequence[Sequence[int]],
    pace: Pace = Pace.STANDARD,
    planned: Sequence[int | None] | None = None,
    failure_sets: Sequence[int | None] | None = None,
) -> tuple[int, ...]:
    """Target value per planned set at the person's ``pace``. ``history`` holds every
    session's per-set values at this ladder step, newest first (as ``progression.assess``
    takes them); ``planned``, in the same order, the sets each one planned, and
    ``failure_sets`` the set each one ran to as many good reps as it could (ADR-0084)."""
    given = [item.rep_min] * item.sets
    misses = [0] * item.sets
    reached = 0  # the most sets a session has planned so far
    counts = planned_counts(history, planned)
    fails = failure_counts(history, failure_sets)
    for values, count, fail in zip(
        reversed(history), reversed(counts), reversed(fails), strict=True
    ):
        done = _performed(item, values, count)
        if (
            fail is not None
            and fail <= min(len(values), len(done))
            and done[fail - 1] >= given[fail - 1]
        ):
            done[fail - 1] = given[fail - 1]  # as many as it could: its target met (ADR-0084)
        # A set's first session at a step is its baseline, never a miss: below the range,
        # targets grow from what was done instead of jumping to the bottom (ADR-0027).
        given[reached : len(done)] = done[reached:]
        reached = max(reached, len(done))
        for n, value in enumerate(done):
            if value >= given[n]:
                given[n], misses[n] = _cap(value + step(item, pace), item), 0
            elif misses[n] + 1 >= MISSES_BEFORE_EASING:
                given[n], misses[n] = _cap(value + 1, item), 0
            else:
                misses[n] += 1  # hold the target
        if 0 < len(done) < item.sets:
            # Sets the day didn't plan weren't replayed; they come back from the nearest set
            # before them, its target and no misses, not from a stale value (ADR-0084).
            dropped = item.sets - len(done)
            given[len(done) :] = [given[len(done) - 1]] * dropped
            misses[len(done) :] = [0] * dropped
    return tuple(given)
