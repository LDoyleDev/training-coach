"""Heart-rate zones (ADR-0055): Karvonen, from resting and max heart rate. Pure logic, no I/O.

Karvonen counts from the heart-rate reserve, max minus resting: zone 2 runs from 60 to 70% of
it above resting. Resting heart rate is the median of the last 7 nights. Max heart rate is the
person's own number when they typed one; otherwise the higher of 208 - 0.7 x age (Tanaka) and
the highest any workout reached, so a hard effort raises it by itself.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median

BANDS = ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0))  # zones 1-5, of reserve
NIGHTS = 7  # resting heart rate is the median of this many recent nights
DEFAULT_REST = 60  # with no nights yet
DEFAULT_MAX = 190  # with no age, no workouts and no number of their own
LONGEST_GAP = timedelta(minutes=5)  # a reading counts until the next one, at most this long
MIN_AGE, MAX_AGE = 10, 100


@dataclass(frozen=True)
class Zones:
    rest: int
    max: int
    bounds: tuple[tuple[int, int], ...]  # (from, to) bpm for zones 1-5; "to" is exclusive

    def zone(self, bpm: float) -> int:
        """The zone a heart rate is in: 1-5, 5 above max too, 0 below zone 1."""
        for number in range(len(self.bounds), 0, -1):
            if bpm >= self.bounds[number - 1][0]:
                return number
        return 0


def karvonen(rest: int, top: int) -> Zones:
    """Zones from resting and max heart rate. A max at or below rest makes no reserve, so it
    is lifted to one beat above."""
    top = max(top, rest + 1)
    reserve = top - rest
    bounds = tuple((round(rest + reserve * lo), round(rest + reserve * hi)) for lo, hi in BANDS)
    return Zones(rest, top, bounds)


def estimated_max(age: int) -> int:
    """208 - 0.7 x age (Tanaka, Monahan and Seals, 2001)."""
    return round(208 - 0.7 * age)


def age(birth_year: int | None, year: int) -> int | None:
    """Age this year, or None without a believable birth year."""
    if birth_year is None or not MIN_AGE <= year - birth_year <= MAX_AGE:
        return None
    return year - birth_year


def max_heart_rate(own: int | None, years: int | None, peak: int | None) -> int:
    """Their own number wins; else the higher of the estimate (190 without an age) and the
    highest a workout reached."""
    if own is not None:
        return own
    estimate = estimated_max(years) if years is not None else DEFAULT_MAX
    return max(estimate, peak or 0)


def resting(nights: Sequence[int]) -> int:
    """The median of the most recent nights, newest first; 60 without any."""
    recent = list(nights[:NIGHTS])
    return round(median(recent)) if recent else DEFAULT_REST


def minutes(readings: Sequence[tuple[datetime, int]], end: datetime, zones: Zones) -> list[int]:
    """Minutes in zones 1-5 from ``(time, bpm)`` readings in time order: each reading lasts
    until the next one or ``end``, at most 5 minutes, so a gap in the data counts for little."""
    seconds = [0.0] * len(BANDS)
    for n, (at, bpm) in enumerate(readings):
        until = readings[n + 1][0] if n + 1 < len(readings) else end
        length = min(max(until - at, timedelta(0)), LONGEST_GAP).total_seconds()
        if (zone := zones.zone(bpm)) > 0:
            seconds[zone - 1] += length
    return [round(s / 60) for s in seconds]
