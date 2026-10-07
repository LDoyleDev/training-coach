"""Training blocks (ADR-0028). Pure logic, no I/O.

From the day blocks were turned on, training alternates 4-week blocks: strength first, then
hypertrophy. Days the bot was paused don't count, so a lost week never shortens a block.
"""

from collections.abc import Collection
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from training_coach.domain.enums import ExerciseKind

BLOCK_DAYS = 28
WEEKS = BLOCK_DAYS // 7


class BlockKind(StrEnum):
    STRENGTH = "strength"
    HYPERTROPHY = "hypertrophy"


@dataclass(frozen=True)
class Block:
    number: int  # 1 for the first block
    kind: BlockKind
    week: int  # 1 to WEEKS within the block


def block_on(day: date, started_on: date, paused: Collection[date] = ()) -> Block | None:
    """The block ``day`` falls in, or None before blocks started. Counted days are the days
    from ``started_on`` up to (not including) ``day`` that weren't paused."""
    if day < started_on:
        return None
    counted = sum(
        1 for n in range((day - started_on).days) if started_on + timedelta(days=n) not in paused
    )
    index = counted // BLOCK_DAYS
    return Block(
        number=index + 1,
        kind=BlockKind.STRENGTH if index % 2 == 0 else BlockKind.HYPERTROPHY,
        week=counted % BLOCK_DAYS // 7 + 1,
    )


def paused_days(changes: list[tuple[date, bool]], until: date) -> set[date]:
    """Days paused, from ``(local date, paused)`` changes in time order, up to ``until``.

    A pause takes effect on the day it was set and lasts until the day it was lifted (that
    day counts again). Repeated changes to the same value change nothing."""
    days: set[date] = set()
    since: date | None = None
    for on, paused in changes:
        if paused and since is None:
            since = on
        elif not paused and since is not None:
            days.update(since + timedelta(days=n) for n in range((on - since).days))
            since = None
    if since is not None:
        days.update(since + timedelta(days=n) for n in range((until - since).days + 1))
    return days


# A strength block (ADR-0028): rep-counted exercises in strength sessions train one ladder step
# harder, at 4-8 reps for 3-4 sets. At the top of a ladder the top step gets a tempo cue.
STRENGTH_REPS = (4, 8)
STRENGTH_SETS = (3, 4)
TOP_STEP_CUE = "3 s lowering, pause at the bottom"


def strength_sets(planned: int) -> int:
    """The planned sets, raised to 3 and capped at 4."""
    low, high = STRENGTH_SETS
    return max(low, min(high, planned))


def history_kind(exercise: ExerciseKind, prescribed: BlockKind) -> BlockKind | None:
    """Which block's history a target or record looks at. Only rep-counted work changes in a
    strength block, so timed and duration exercises keep one history across blocks (None)."""
    return prescribed if exercise is ExerciseKind.REPS else None
