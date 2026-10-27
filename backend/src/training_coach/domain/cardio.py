"""What a cardio log was, read from the words of a typed or spoken log (ux-flow-plan A1):
"walked 45 min" is a walk, "cycled for an hour" a bike ride. Only an unambiguous mention
counts; anything else leaves the activity empty.

And what else a cardio log can carry (ADR-0067): how hard it felt (session RPE), the
distance, the average and highest heart rate and when it started. Pace is worked out from
minutes and distance, never stored: a ride shows its speed instead.

Which of the two a log is, zone 2 or moderate, the person picks. The coach may suggest one
from their own heart-rate zones (ADR-0067 addendum of 2026-10-24), never decide it."""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from training_coach.domain.enums import CardioActivity
from training_coach.domain.zones import Zones

# The exercises logged in minutes whose log can carry an activity (plan.toml slugs).
TIMED = ("zone2", "moderate-cardio")
Timed = Literal["zone2", "moderate-cardio"]
ZONE_2 = 2  # the heart-rate zone (ADR-0055) zone 2 cardio is named after

WORDS: dict[CardioActivity, frozenset[str]] = {
    CardioActivity.WALK: frozenset({"walk", "walks", "walked", "walking"}),
    CardioActivity.HIKE: frozenset({"hike", "hikes", "hiked", "hiking"}),
    CardioActivity.JOG: frozenset({"jog", "jogs", "jogged", "jogging"}),
    CardioActivity.RUN: frozenset({"run", "runs", "ran", "running"}),
    CardioActivity.BIKE: frozenset(
        {"bike", "biked", "biking", "cycle", "cycled", "cycling", "ride", "rode"}
    ),
    CardioActivity.SWIM: frozenset({"swim", "swam", "swimming"}),
    CardioActivity.ROW: frozenset({"row", "rowed", "rowing"}),
    CardioActivity.STAIRS: frozenset({"stairs", "stair"}),
}


def activity_in(text: str) -> CardioActivity | None:
    """The one activity ``text`` names, or None when it names none or several."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    found = [activity for activity, forms in WORDS.items() if words & forms]
    return found[0] if len(found) == 1 else None


EFFORT = (1, 10)  # session RPE: 1 very easy, 10 all out (Foster)
HEART_RATE = (30, 230)  # bpm, average or highest
MAX_DISTANCE_M = 300_000  # 300 km: a longer single session is a mistake


@dataclass(frozen=True)
class Details:
    """What a cardio log carries besides its minutes; each part only when someone gave it."""

    effort: int | None = None
    distance_m: int | None = None
    avg_hr: int | None = None
    max_hr: int | None = None
    started_at: datetime | None = None  # UTC

    def __bool__(self) -> bool:
        return any(v is not None for v in vars(self).values())


NO_DETAILS = Details()  # a log with only its minutes


def details_problem(details: Details, *, rounds: bool) -> str | None:
    """Why ``details`` can't be saved, or None. HIIT counts rounds, so it has no distance."""
    low, high = EFFORT
    if details.effort is not None and not low <= details.effort <= high:
        return f"effort must be between {low} and {high}"
    if details.distance_m is not None:
        if rounds:
            return "HIIT is counted in rounds: no distance"
        if not 1 <= details.distance_m <= MAX_DISTANCE_M:
            return f"distance must be between 0 and {MAX_DISTANCE_M // 1000} km"
    low, high = HEART_RATE
    for name, bpm in (("average", details.avg_hr), ("highest", details.max_hr)):
        if bpm is not None and not low <= bpm <= high:
            return f"{name} heart rate must be between {low} and {high}"
    if (
        details.avg_hr is not None
        and details.max_hr is not None
        and details.max_hr < details.avg_hr
    ):
        return "highest heart rate can't be below the average"
    return None


def pace(minutes: int, distance_m: int | None) -> int | None:
    """Seconds per km, or None without a distance."""
    if distance_m is None or distance_m <= 0 or minutes <= 0:
        return None
    return round(minutes * 60 * 1000 / distance_m)


def speed(minutes: int, distance_m: int | None) -> float | None:
    """Km per hour, or None without a distance: a ride is read by its speed, not its pace."""
    if distance_m is None or distance_m <= 0 or minutes <= 0:
        return None
    return distance_m * 60 / (minutes * 1000)


def by_speed(activity: CardioActivity | None) -> bool:
    """Whether a log of this activity shows km/h rather than min/km."""
    return activity is CardioActivity.BIKE


def suggested(avg_hr: int, zones: Zones) -> Timed:
    """The kind an average heart rate suggests: zone 2 up to the top of zone 2, moderate
    above it. Only a suggestion; the person picks."""
    return "zone2" if zones.zone(avg_hr) <= ZONE_2 else "moderate-cardio"


def load(minutes: int, effort: int | None) -> int | None:
    """Session load: minutes times RPE (Foster 2001), comparable whatever was worn."""
    return minutes * effort if effort is not None else None


def left(done: int, target: int | None) -> int | None:
    """Minutes still to go to a cardio target (ADR-0079): 0 once reached, None without one."""
    return None if target is None else max(0, target - done)


EXTRA_CARDIO = (0, 600)  # minutes a week a person can add to the targets (ADR-0079)
Range = tuple[int, int]


@dataclass(frozen=True)
class Targets:
    """Cardio targets for 7 days (ADR-0079), each a range of minutes; None with nothing to aim
    for."""

    zone2: Range | None
    total: Range | None  # all cardio, any zone


def targets(zone2: Range | None, moderate: Range | None, extra: int) -> Targets:
    """The cycle's zone 2 prescriptions, and all its cardio in minutes (HIIT counts rounds, so
    it isn't here), each plus the person's extra cardio a week: walks or rides outside the
    sessions, easy by nature, so they add to zone 2 as well."""
    z2, mod = zone2 or (0, 0), moderate or (0, 0)
    return Targets(
        (z2[0] + extra, z2[1] + extra) if zone2 or extra else None,
        (z2[0] + mod[0] + extra, z2[1] + mod[1] + extra) if zone2 or moderate or extra else None,
    )
