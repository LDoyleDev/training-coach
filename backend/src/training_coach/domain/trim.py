"""A session trimmed to fit the minutes a person has today (ADR-0082). Pure logic, no I/O.

The estimate lives in services (each set's work and the rest after it, by the rules the session
runs), so the trim takes it as a callable: the minutes of work, without the warm-up, for given
set counts and duration minutes. A session fits when that estimate, rounded as the overview
shows it, plus the warm-up is no more than the minutes. Each rule applies only while the
session still doesn't fit, in this order:

1. fourth and later sets go, from every exercise at once;
2. third sets go, from every exercise at once, so every exercise keeps two;
3. a duration item (cardio, ``duration_min``) shortens a minute at a time, the longest first,
   never below 10 minutes;
4. whole exercises go, one at a time, by ``_group``: covered accessory work first, main
   patterns no other exercise trains last, the later exercise first within a group. An
   exercise pinned with Keep for the day never goes;
5. never under one set of an exercise that stays, and never the last exercise.

Items are never removed, so every set keeps its index: a dropped item has 0 sets. Rests are
not the trim's: the estimate runs them by ``rest.rests`` over the trimmed counts, which keeps
60 s or more between two rounds for the same muscle; the trim changes counts, never a rest.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from training_coach.domain.muscles import Muscle, Pattern

WARM_UP_MINUTES = 5  # J.4, ADR-0065 addendum
RAMP_MINUTES = 2  # one or two easy sets of the first exercise (ADR-0082)
RAMP_UP_TO = 30  # at this many minutes or fewer, ramp sets replace the warm-up
FULL_WARM_UP_LEVEL = 3  # a first exercise at this level or below keeps the warm-up (ADR-0083)
MOST_SETS = (3, 2)  # rules 1 and 2: the sets each exercise keeps
SHORTEST_DURATION = 10  # rule 3: a duration item's floor, in minutes

# Single-joint and accessory work; every other pattern, cardio included, is main work.
ACCESSORY = frozenset({Pattern.ISOLATION, Pattern.CORE, Pattern.CARRY, Pattern.MOBILITY})

# (set counts, duration minutes) per item -> minutes of work, warm-up not included
Estimate = Callable[[tuple[int, ...], tuple[int | None, ...]], float]


class WarmUp(StrEnum):
    NONE = "none"  # a session without one (conditioning)
    FULL = "full"  # the 5-minute warm-up
    RAMP = "ramp"  # easy sets of the first exercise at about half its target, not logged


WARM_UP = {WarmUp.NONE: 0, WarmUp.FULL: WARM_UP_MINUTES, WarmUp.RAMP: RAMP_MINUTES}


@dataclass(frozen=True)
class Item:
    """What the trim needs to know about one item of the session."""

    sets: int  # as planned
    pattern: Pattern
    primes: frozenset[Muscle] = frozenset()  # the muscles it counts 1 for
    minutes: int | None = None  # a duration item's minutes; None for reps or seconds
    keep: bool = False  # pinned with Keep for the day: never dropped
    level: int | None = None  # its step's level (ADR-0083); None reads as 4 or above


@dataclass(frozen=True)
class Trimmed:
    sets: tuple[int, ...]  # per item; 0 means dropped
    durations: tuple[int | None, ...]  # a duration item's minutes, maybe shortened; else None
    dropped: tuple[int, ...]  # the items dropped, in the order they went
    warm_up: WarmUp
    minutes: int  # about how long, warm-up included
    fits: bool

    @property
    def shortest(self) -> int | None:
        """The overview's "the shortest this session gets is N minutes"; None when it fits."""
        return None if self.fits else self.minutes


def warm_up(items: Sequence[Item], sets: Sequence[int], minutes: int | None) -> WarmUp:
    """The 5-minute warm-up, or ramp sets at ``RAMP_UP_TO`` minutes or fewer, unless the first
    exercise still in the session is at ``FULL_WARM_UP_LEVEL`` or below (ADR-0082)."""
    if minutes is None or minutes > RAMP_UP_TO:
        return WarmUp.FULL
    first = next((item for item, n in zip(items, sets, strict=True) if n > 0), None)
    if first is not None and first.level is not None and first.level <= FULL_WARM_UP_LEVEL:
        return WarmUp.FULL
    return WarmUp.RAMP


def _group(items: Sequence[Item], staying: Sequence[int], i: int) -> int:
    """Rule 4's drop order, lowest first: accessory work whose prime movers the other
    exercises still in the session train too; other accessory work; main patterns so covered;
    main patterns no other exercise trains. An exercise without prime movers isn't covered."""
    others = frozenset[Muscle]().union(*(items[j].primes for j in staying if j != i))
    covered = bool(items[i].primes) and items[i].primes <= others
    return (0 if covered else 1) + (0 if items[i].pattern in ACCESSORY else 2)


def _next_drop(items: Sequence[Item], sets: Sequence[int]) -> int | None:
    staying = [i for i, n in enumerate(sets) if n > 0]
    if len(staying) < 2:  # a session of nothing fits any minutes but isn't a session
        return None
    candidates = [i for i in staying if not items[i].keep]
    if not candidates:
        return None
    return min(candidates, key=lambda i: (_group(items, staying, i), -i))


def _longest(durations: Sequence[int | None], sets: Sequence[int]) -> int | None:
    """The duration item to shorten by a minute: the longest above the floor, the later on a
    tie; None when every one is at the floor."""
    long = [
        (minutes, i)
        for i, (minutes, n) in enumerate(zip(durations, sets, strict=True))
        if minutes is not None and minutes > SHORTEST_DURATION and n > 0
    ]
    return max(long)[1] if long else None


def trim(
    items: Sequence[Item],
    minutes: int | None,
    estimate: Estimate,
    *,
    has_warm_up: bool = True,
) -> Trimmed:
    """``items`` trimmed to fit ``minutes``, warm-up included; ``minutes`` None is as planned
    and changes nothing. ``has_warm_up`` is False for a session without one (conditioning).

    When even the floor doesn't fit, the result says so (``fits`` False) and how long the floor
    is (``shortest``), which the overview offers instead."""
    sets = [item.sets for item in items]
    durations = [item.minutes for item in items]
    dropped: list[int] = []

    def now() -> Trimmed:
        how = warm_up(items, sets, minutes) if has_warm_up else WarmUp.NONE
        total = round(estimate(tuple(sets), tuple(durations))) + WARM_UP[how]
        fits = minutes is None or total <= minutes
        return Trimmed(tuple(sets), tuple(durations), tuple(dropped), how, total, fits)

    result = now()
    for most in MOST_SETS:  # rules 1 and 2
        if result.fits:
            return result
        sets[:] = [min(n, most) for n in sets]
        result = now()
    while not result.fits and (i := _longest(durations, sets)) is not None:  # rule 3
        durations[i] = (durations[i] or 0) - 1
        result = now()
    while not result.fits and (i := _next_drop(items, sets)) is not None:  # rule 4
        sets[i] = 0
        dropped.append(i)
        result = now()
    return result
