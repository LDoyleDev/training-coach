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


def _performed(item: Prescription, values: Sequence[int]) -> list[int]:
    """One value per planned set. Missing sets start from the weakest logged set."""
    done = [_cap(v, item) for v in values[: item.sets]]
    if not done:
        return [0] * item.sets
    return done + [min(done)] * (item.sets - len(done))


def targets(
    item: Prescription, history: Sequence[Sequence[int]], pace: Pace = Pace.STANDARD
) -> tuple[int, ...]:
    """Target value per planned set at the person's ``pace``. ``history`` holds every
    session's per-set values at this ladder step, newest first (as ``progression.assess``
    takes them)."""
    given = [item.rep_min] * item.sets
    misses = [0] * item.sets
    for index, values in enumerate(reversed(history)):
        done = _performed(item, values)
        if index == 0:
            # The first session at a step is the baseline, never a miss: below the range,
            # targets grow from what was done instead of jumping to the bottom (ADR-0027).
            given = list(done)
        for n in range(item.sets):
            if done[n] >= given[n]:
                given[n], misses[n] = _cap(done[n] + step(item, pace), item), 0
            elif misses[n] + 1 >= MISSES_BEFORE_EASING:
                given[n], misses[n] = _cap(done[n] + 1, item), 0
            else:
                misses[n] += 1  # hold the target
    return tuple(given)
