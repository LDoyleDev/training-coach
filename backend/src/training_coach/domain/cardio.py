"""What a cardio log was, read from the words of a typed or spoken log (ux-flow-plan A1):
"walked 45 min" is a walk, "cycled for an hour" a bike ride. Only an unambiguous mention
counts; anything else leaves the activity empty.

And what else a cardio log can carry (ADR-0067): how hard it felt (session RPE), the
distance, the average and highest heart rate and when it started. Pace is worked out from
minutes and distance, never stored."""

import re
from dataclasses import dataclass
from datetime import datetime

from training_coach.domain.enums import CardioActivity

# The exercises logged in minutes whose log can carry an activity (plan.toml slugs).
TIMED = ("zone2", "moderate-cardio")

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


def load(minutes: int, effort: int | None) -> int | None:
    """Session load: minutes times RPE (Foster 2001), comparable whatever was worn."""
    return minutes * effort if effort is not None else None
