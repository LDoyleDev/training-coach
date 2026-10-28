"""Closed sets of values shared by the domain and the database."""

from enum import StrEnum


class ExerciseKind(StrEnum):
    """How an exercise is measured."""

    REPS = "reps"
    SECONDS = "seconds"
    DURATION_MIN = "duration_min"


class WorkoutStatus(StrEnum):
    """Outcome of a workout.

    ``done`` and ``rest`` advance the session queue; ``skipped`` does not (ADR-0006).
    """

    DONE = "done"
    REST = "rest"
    SKIPPED = "skipped"


class Side(StrEnum):
    """Side of a set. ``both`` for bilateral exercises; never NULL, so uniqueness holds."""

    BOTH = "both"
    LEFT = "left"
    RIGHT = "right"


class CardioActivity(StrEnum):
    """What a logged cardio session was (ux-flow-plan A1). Optional on a workout."""

    WALK = "walk"
    HIKE = "hike"
    JOG = "jog"
    RUN = "run"
    BIKE = "bike"
    SWIM = "swim"
    ROW = "row"
    STAIRS = "stairs"
    OTHER = "other"


class Sound(StrEnum):
    """What every guided timer plays at each change (ADR-0062, ADR-0074). A per-person setting;
    the boxing-ring bell is everyone's default."""

    RING = "ring"
    CHIME = "chime"
    BEEP = "beep"
    WOOD = "wood"
    BELL = "bell"
    NONE = "none"


class Place(StrEnum):
    """Where a workout is done (ADR-0071): at home, with the person's own kit, or at a gym,
    which has everything. A session can hold a version for each."""

    HOME = "home"
    GYM = "gym"


class Places(StrEnum):
    """Where a person trains, a setting (ADR-0071). Everyone starts at home."""

    HOME = "home"
    GYM = "gym"
    BOTH = "both"
