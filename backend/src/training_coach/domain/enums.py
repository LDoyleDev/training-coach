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
    """Side for unilateral exercises; ``None`` in the database means both or not applicable."""

    LEFT = "left"
    RIGHT = "right"
