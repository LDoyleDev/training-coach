"""What a cardio log was, read from the words of a typed or spoken log (ux-flow-plan A1):
"walked 45 min" is a walk, "cycled for an hour" a bike ride. Only an unambiguous mention
counts; anything else leaves the activity empty."""

import re

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
