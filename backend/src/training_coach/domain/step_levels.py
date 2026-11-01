"""What a ladder step asks of a person (ADR-0083). Pure logic, no I/O.

Every step has a level on one scale across all ladders, so a person's general level can pick a
sensible start everywhere. Levels place a person; they never cap progress: the top is open, and
steps added above today's top stay at the highest level. Marks say what a step asks of the body
beyond its level, for the preferences ("Keep me off the floor", "No kneeling", "No jumping or
running", "No hanging", "Easy on my knees"); balance marks a fall risk.

Not a person's "level" on a ladder elsewhere in the code (the step they are on, ADR-0075).
"""

from collections.abc import Sequence
from enum import IntEnum, StrEnum


class StepLevel(IntEnum):
    """Who a step is for (ADR-0083's table)."""

    SUPPORTED = 1  # stands up from a chair only with the hands; walking a few minutes is hard
    STARTING = 2  # stands up without the hands; no push-up from the knees yet; walks 10 minutes
    BUILDING = 3  # knee push-ups, a bodyweight squat, a 20-minute walk
    REGULAR = 4  # 10 push-ups, a first pull-up: the plan's bottom steps before ADR-0083
    STRONG = 5  # the plan's middle steps
    ADVANCED = 6  # its top steps, and everything above


class Mark(StrEnum):
    """What a step asks of the body beyond its level."""

    FLOOR = "floor"  # lying on the floor, or getting down to it and up again
    KNEELING = "kneeling"  # weight on a knee
    IMPACT = "impact"  # jumps or running, every way the step can be done
    HANGING = "hanging"  # from a bar
    BALANCE = "balance"  # on one leg, or balance work without a hold: a fall risk
    # Deep knee bending, every way the step can be done: a loaded or full-depth squat, one leg
    # below chair height, a full-range split squat or lunge, a Nordic (#540). A squat to a
    # chair, a low step and a bike are not.
    KNEES = "knees"


def first_fall(levels: Sequence[int]) -> int | None:
    """The index of the first level lower than the one before it, or None when a ladder's
    levels never fall (easiest first, as ladders run)."""
    return next((i for i in range(1, len(levels)) if levels[i] < levels[i - 1]), None)
