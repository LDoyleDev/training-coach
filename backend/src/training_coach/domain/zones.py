"""Heart-rate zones (ADR-0055): Karvonen, from resting and max heart rate. Pure logic, no I/O.

Karvonen counts from the heart-rate reserve, max minus resting: zone 2 runs from 60 to 70% of
it above resting. Resting heart rate is the median of the last 7 nights. Max heart rate is the
person's own number when they typed one; otherwise the higher of 208 - 0.7 x age (Tanaka) and
the highest any workout held for three minutes, so a hard effort raises it by itself, but one
odd reading or a made-up workout from a stolen ingest secret can't take it far (2026-10-24).
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
# A workout raises max heart rate only with what it held this many minutes in a row: an optical
# band's one-minute glitch (cadence lock, a loose strap) isn't a max, a hard finish holds.
SUSTAIN = 3
# And by at most this much over the estimate: an age formula misses by about 10 bpm for most
# people, so 20 covers a real high max; anyone above that types their own number.
RAISE_LIMIT = 20


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
    peak a workout held, as ``counted_peak`` counts it."""
    if own is not None:
        return own
    return max(_estimate(years), peak or 0)


def _estimate(years: int | None) -> int:
    return estimated_max(years) if years is not None else DEFAULT_MAX


def counted_peak(years: int | None, peak: int | None) -> int | None:
    """A workout's peak as it counts toward max heart rate: at most ``RAISE_LIMIT`` over the
    estimate."""
    return None if peak is None else min(peak, _estimate(years) + RAISE_LIMIT)


def sustained(readings: Sequence[tuple[datetime, float]], hold: int = SUSTAIN) -> int | None:
    """The highest heart rate held ``hold`` minutes in a row, from per-minute ``(minute,
    bpm)`` readings in time order, one per minute: the best of the lowest of each run of
    ``hold`` back-to-back minutes. None without such a run."""
    best: int | None = None
    for n in range(len(readings) - hold + 1):
        run = readings[n : n + hold]
        if run[-1][0] - run[0][0] == timedelta(minutes=hold - 1):
            low = round(min(bpm for _, bpm in run))
            best = low if best is None else max(best, low)
    return best


def resting(nights: Sequence[int]) -> int:
    """The median of the most recent nights, newest first; 60 without any."""
    recent = list(nights[:NIGHTS])
    return round(median(recent)) if recent else DEFAULT_REST


def measured(readings: Sequence[tuple[datetime, int]], end: datetime, zones: Zones) -> list[int]:
    """Minutes below zone 1 and in zones 1-5 from ``(time, bpm)`` readings in time order: each
    reading lasts until the next one or ``end``, at most 5 minutes, so a gap in the data counts
    for little."""
    seconds = [0.0] * (len(BANDS) + 1)
    for n, (at, bpm) in enumerate(readings):
        until = readings[n + 1][0] if n + 1 < len(readings) else end
        seconds[zones.zone(bpm)] += min(max(until - at, timedelta(0)), LONGEST_GAP).total_seconds()
    return [round(s / 60) for s in seconds]


def minutes(readings: Sequence[tuple[datetime, int]], end: datetime, zones: Zones) -> list[int]:
    """Minutes in zones 1-5 (``measured`` without the minutes below zone 1)."""
    return measured(readings, end, zones)[1:]


@dataclass(frozen=True)
class Split:
    """Cardio minutes by zone (ADR-0079). ``measured`` is below zone 1 ("easy") and zones 1-5,
    from heart rate; minutes without heart rate count in the zone the person logged them as:
    zone 2, or zone 3 and above for moderate cardio."""

    measured: tuple[int, ...] = (0,) * (len(BANDS) + 1)
    zone2_unmeasured: int = 0
    harder_unmeasured: int = 0  # "zone 3+ (no heart rate)"

    @property
    def total(self) -> int:
        return sum(self.measured) + self.zone2_unmeasured + self.harder_unmeasured

    @property
    def zone2(self) -> int:
        """Zone 2 minutes: from heart rate, and logged as zone 2 without it."""
        return self.measured[2] + self.zone2_unmeasured

    def __add__(self, other: "Split") -> "Split":
        return Split(
            tuple(a + b for a, b in zip(self.measured, other.measured, strict=True)),
            self.zone2_unmeasured + other.zone2_unmeasured,
            self.harder_unmeasured + other.harder_unmeasured,
        )


def split(total: int, harder: bool, found: Sequence[int] | None = None) -> Split:
    """A workout's ``total`` minutes by zone: ``found`` (``measured``) where it has heart rate,
    trimmed from the largest zones when rounding made it more than ``total``; the rest, or all
    of it without heart rate, in the zone it was logged as (zone 3+ when ``harder``)."""
    zone_minutes = list(found) if found is not None else [0] * (len(BANDS) + 1)
    over = max(0, sum(zone_minutes) - total)
    for n in sorted(range(len(zone_minutes)), key=lambda n: -zone_minutes[n]):
        take = min(zone_minutes[n], over)
        zone_minutes[n] -= take
        over -= take
    rest = total - sum(zone_minutes)
    return Split(tuple(zone_minutes), 0 if harder else rest, rest if harder else 0)
