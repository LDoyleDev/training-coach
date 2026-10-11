"""Band data from Health Connect (ADR-0054): what the records mean, in plain numbers. Pure logic,
no I/O.

Health Connect names exercise types and sleep stages by AndroidX constants, sent as strings
("79" is walking, "4" light sleep). Heart rate arrives per sample or per N-minute bucket and is
kept per minute. A day's steps are summed per local day; resting heart rate is the lowest
minute of a night.
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from training_coach.domain.daily_check import Sleep
from training_coach.domain.enums import CardioActivity

# AndroidX ExerciseSessionRecord.EXERCISE_TYPE_* for the cardio this plan logs. Anything else
# (strength, yoga, football...) is kept but never offered as cardio.
EXERCISE_TYPES: dict[int, CardioActivity] = {
    79: CardioActivity.WALK,
    37: CardioActivity.HIKE,
    56: CardioActivity.RUN,
    57: CardioActivity.RUN,  # treadmill
    8: CardioActivity.BIKE,
    9: CardioActivity.BIKE,  # stationary
    73: CardioActivity.SWIM,  # open water
    74: CardioActivity.SWIM,  # pool
    53: CardioActivity.ROW,
    54: CardioActivity.ROW,  # machine
    68: CardioActivity.STAIRS,
    69: CardioActivity.STAIRS,  # machine
    25: CardioActivity.OTHER,  # elliptical
}

# AndroidX SleepSessionRecord.STAGE_TYPE_*.
AWAKE, SLEEPING, OUT_OF_BED, LIGHT, DEEP, REM, AWAKE_IN_BED = 1, 2, 3, 4, 5, 6, 7

NIGHT = (time(0), time(6))  # where resting heart rate is looked for without a sleep session
MIN_NIGHT_MINUTES = 20  # fewer minutes of heart rate in a night say nothing about rest


def activity_for(exercise_type: int) -> CardioActivity | None:
    """What an exercise session was as cardio, or None when it isn't cardio."""
    return EXERCISE_TYPES.get(exercise_type)


@dataclass(frozen=True)
class SleepMinutes:
    asleep: int
    awake: int
    light: int
    deep: int
    rem: int


def sleep_minutes(total_seconds: int, stages: Iterable[tuple[int, int]]) -> SleepMinutes:
    """Minutes per stage from ``(stage, seconds)`` pairs. "Sleeping" without detail counts as
    light; unknown stages count for nothing. With no stages at all, the session was asleep."""
    seconds: dict[str, int] = defaultdict(int)
    staged = False
    for stage, length in stages:
        staged = True
        if stage in (LIGHT, SLEEPING):
            seconds["light"] += length
        elif stage == DEEP:
            seconds["deep"] += length
        elif stage == REM:
            seconds["rem"] += length
        elif stage in (AWAKE, AWAKE_IN_BED, OUT_OF_BED):
            seconds["awake"] += length
    if not staged:
        return SleepMinutes(total_seconds // 60, 0, 0, 0, 0)
    light, deep, rem = (seconds[k] // 60 for k in ("light", "deep", "rem"))
    return SleepMinutes(light + deep + rem, seconds["awake"] // 60, light, deep, rem)


@dataclass(frozen=True)
class Minute:
    """Heart rate in one minute: the average, the lowest and the highest beat rate."""

    at: datetime  # the minute's start, UTC
    bpm: int
    low: int
    high: int


def per_minute(readings: Iterable[tuple[datetime, float, float, float]]) -> list[Minute]:
    """``(time, average, low, high)`` readings, samples or buckets, as one row per minute: a
    minute with several readings averages them and keeps the extremes."""
    found: dict[datetime, list[tuple[float, float, float]]] = defaultdict(list)
    for at, average, low, high in readings:
        start = at.astimezone(UTC).replace(second=0, microsecond=0)
        found[start].append((average, low, high))
    return [
        Minute(
            at,
            round(sum(r[0] for r in rows) / len(rows)),
            round(min(r[1] for r in rows)),
            round(max(r[2] for r in rows)),
        )
        for at, rows in sorted(found.items())
    ]


def steps_by_day(intervals: Iterable[tuple[datetime, int]], tz: ZoneInfo) -> dict[date, int]:
    """Step counts summed per local day of each interval's start."""
    days: dict[date, int] = defaultdict(int)
    for start, count in intervals:
        days[start.astimezone(tz).date()] += count
    return dict(days)


def night(day: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """00:00 to 06:00 local time on ``day``, in UTC."""
    start, end = (datetime.combine(day, t, tzinfo=tz).astimezone(UTC) for t in NIGHT)
    return start, end


def resting(minutes: Sequence[Minute]) -> int | None:
    """Resting heart rate from a night's minutes: the lowest minute's average, or None when
    there are too few minutes to tell."""
    if len(minutes) < MIN_NIGHT_MINUTES:
        return None
    return min(m.bpm for m in minutes)


ZONE2, MODERATE = "zone2", "moderate-cardio"  # the plan's cardio exercises (plan.toml)
HARD_WITHOUT_HEART_RATE = frozenset({CardioActivity.RUN, CardioActivity.JOG, CardioActivity.STAIRS})
MIN_COUNTED = 5  # minutes: less isn't worth offering


def counted_as(
    activity: CardioActivity, minutes: int, zone_minutes: Sequence[int] | None
) -> tuple[str, int] | None:
    """The cardio exercise a band workout counts as, and for how many minutes (ADR-0054).

    With heart rate: zone 2 when it spent at least as long in zone 2 as in zones 3-5, for its
    zone 2 minutes only; moderate otherwise, for all of it. Without: a run or stairs is
    moderate, anything else zone 2, for all of it. None when that is under 5 minutes."""
    if zone_minutes is not None:
        zone2, harder = zone_minutes[1], sum(zone_minutes[2:])
        found = (ZONE2, zone2) if zone2 >= harder else (MODERATE, minutes)
    elif activity in HARD_WITHOUT_HEART_RATE:
        found = (MODERATE, minutes)
    else:
        found = (ZONE2, minutes)
    return found if found[1] >= MIN_COUNTED else None


def offer_text(activity: CardioActivity, minutes: int, zone_minutes: Sequence[int] | None) -> str:
    """The question, e.g. "Walk, 46 min, 38 in zone 2 - count it?"."""
    name = "Cardio" if activity is CardioActivity.OTHER else activity.value.capitalize()
    if zone_minutes is None:
        return f"{name}, {minutes} min - count it?"
    if zone_minutes[1] >= sum(zone_minutes[2:]):
        return f"{name}, {minutes} min, {zone_minutes[1]} in zone 2 - count it?"
    return f"{name}, {minutes} min, {sum(zone_minutes[2:])} in zones 3-5 - count it?"


def within(moment: datetime, now: datetime, back: timedelta, ahead: timedelta) -> bool:
    """Whether a record's time is believable: not older than ``back``, not ahead of ``now``."""
    return now - back <= moment <= now + ahead


GOOD_SLEEP, OK_SLEEP = 7 * 60, 6 * 60  # minutes asleep


def sleep_answer(asleep: int) -> Sleep:
    """The daily check's sleep answer a night suggests (ADR-0054): 7 hours or more good, 6 to
    7 OK, less poor. Only a suggestion: the person still taps it."""
    if asleep >= GOOD_SLEEP:
        return Sleep.GOOD
    return Sleep.OK if asleep >= OK_SLEEP else Sleep.POOR


def hours(minutes: int) -> str:
    """440 -> "7 h 20 min"."""
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if h and m else f"{h} h" if h else f"{m} min"
