"""How long a guided session's sets take (ADR-0061).

Each set of a guided session carries two times from the phone: when its screen appeared and
when it was confirmed. They are checked here before they are kept, and a session's time, its
time on sets and resting, and its usual time are worked out from them.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import pairwise

SLACK = timedelta(minutes=1)  # a phone's clock a little ahead of the server's
MAX_AGE = timedelta(hours=36)  # a session resumed the next morning still has its times


def plausible(started_at: datetime, done_at: datetime, now: datetime) -> bool:
    """Whether a set's times can be kept: the start before the end, neither in the future
    (beyond ``SLACK``) and both within ``MAX_AGE``. Times failing this are dropped, never the
    set, so a phone with a wrong clock never stops a log."""
    return now - MAX_AGE <= started_at <= done_at <= now + SLACK


BREAK = timedelta(minutes=10)  # a longer gap between sets is a break, not a rest
USUAL_OF = 5  # the usual time is the median of the last this many timed sessions
PACE_FROM = 3  # timed sessions done as planned before an estimate takes the person's pace


@dataclass(frozen=True)
class SetTime:
    started_at: datetime
    done_at: datetime


@dataclass(frozen=True)
class Timing:
    """How a timed session went: ``total`` is ``on_sets + resting``; breaks don't count."""

    total: timedelta
    on_sets: timedelta
    resting: timedelta
    breaks: int
    on_break: timedelta


def timing(sets: Iterable[SetTime]) -> Timing | None:
    """How long a session's sets and the rests between them took, or None with no timed set.

    A set runs from its screen appearing to its confirm; the rest before it is the gap since the
    set before was confirmed. A gap longer than ``BREAK`` is a break (Leave, the phone put away)
    and is left out of the total. Sets that overlap (one fixed out of order) rest nothing."""
    ordered = sorted(sets, key=lambda s: s.started_at)
    if not ordered:
        return None
    on_sets = sum((s.done_at - s.started_at for s in ordered), timedelta())
    resting = on_break = timedelta()
    breaks = 0
    for before, after in pairwise(ordered):
        gap = max(after.started_at - before.done_at, timedelta())
        if gap > BREAK:
            breaks += 1
            on_break += gap
        else:
            resting += gap
    return Timing(on_sets + resting, on_sets, resting, breaks, on_break)


def minutes(span: timedelta) -> int:
    """A span in whole minutes, rounded to the nearest; at least 1 for any time at all."""
    whole = round(span / timedelta(minutes=1))
    return max(whole, 1) if span > timedelta() else 0


def usual(totals: Sequence[timedelta]) -> timedelta | None:
    """The usual time of a session: the median of its last ``USUAL_OF`` timed totals, most
    recent last; None before the first."""
    recent = sorted(totals[-USUAL_OF:])
    if not recent:
        return None
    middle = len(recent) // 2
    if len(recent) % 2:
        return recent[middle]
    return (recent[middle - 1] + recent[middle]) / 2


def pace(totals: Sequence[timedelta], estimate: float) -> float:
    """How the person's time on a session compares with its plain ``estimate`` in minutes
    (ADR-0082): their usual over the estimate, both without the warm-up and breaks. 1.0 before
    ``PACE_FROM`` timed sessions, or with nothing to compare."""
    typical = usual(totals)
    if typical is None or len(totals) < PACE_FROM or estimate <= 0:
        return 1.0
    return typical / timedelta(minutes=estimate)
