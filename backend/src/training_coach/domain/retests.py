"""When baseline tests and retests are due (D4, #95, ADR-0038). Pure logic, no I/O.

A round of tests is two test days, day 1 then day 2 on a later day. While a round is due, its
test day takes the place of the next session: the queue waits, so the order is kept and
everything shifts by the days the tests take (ADR-0006).

- With blocks on, a round is due from the start of each block (ADR-0028).
- With blocks off, a round is due 4 weeks after the last round's day 1.
- The first round, the baseline, is started by hand (from the web app's tests page): nothing is
  due until a first test day exists, so the schedule only changes once Liam has begun. Its
  day 2 is then due like any other.
"""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from training_coach.domain.blocks import BLOCK_DAYS, block_on

RETEST_DAYS = 28  # with blocks off


@dataclass(frozen=True)
class PastTest:
    on: date
    day: int  # 1 or 2


def block_start(day: date, started_on: date, paused: Collection[date] = ()) -> date | None:
    """The first day of the block ``day`` falls in, or None before blocks started."""
    block = block_on(day, started_on, paused)
    if block is None:
        return None
    needed = (block.number - 1) * BLOCK_DAYS  # counted days before the block's first day
    start, counted = started_on, 0
    while counted < needed:
        if start not in paused:
            counted += 1
        start += timedelta(days=1)
    return start


def due(on: date, done: Sequence[PastTest], round_start: date | None) -> int | None:
    """The test day due on ``on`` (1 or 2), or None. ``round_start`` is the start of the
    current block with blocks on, else None (the 4-week cadence)."""
    firsts = sorted(t.on for t in done if t.day == 1 and t.on <= on)
    if not firsts:
        return None  # the baseline hasn't been started
    if round_start is not None:
        current = [d for d in firsts if d >= round_start]
        if not current:
            return 1
        day_1 = current[-1]
    else:
        if on >= firsts[-1] + timedelta(days=RETEST_DAYS):
            return 1
        day_1 = firsts[-1]
    seconds = [t.on for t in done if t.day == 2 and day_1 <= t.on <= on]
    if not seconds and on > day_1:
        return 2
    return None


def name(day: int, done: Sequence[PastTest]) -> str:
    """ "Baseline tests, day 1" before any round is complete, else "Retest, day 1"."""
    complete = any(t.day == 2 for t in done)
    return f"{'Retest' if complete else 'Baseline tests'}, day {day}"
