"""What was logged on a day, for Today's day view (ADR-0068): each workout with its session,
exercises, steps and sets, and the band's numbers for a run it counted. Read-only. Callers
pass a session bound to the user (ADR-0029)."""

from dataclasses import dataclass, replace
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Exercise,
    HabitCheck,
    ImportedWorkout,
    LadderStep,
    SessionTemplate,
    SetLog,
    User,
    Workout,
)
from training_coach.db.session import bound_user
from training_coach.domain.cardio import pace, speed
from training_coach.domain.day_view import LoggedExercise as Grouped
from training_coach.domain.day_view import LoggedSet, group
from training_coach.domain.enums import ExerciseKind, WorkoutStatus
from training_coach.domain.queue import local_date
from training_coach.services import cardio_totals

UNITS = {ExerciseKind.REPS: "reps", ExerciseKind.SECONDS: "seconds"}


@dataclass(frozen=True)
class LoggedExercise:
    name: str
    unit: str  # reps | seconds | minutes
    step: str  # the ladder step it was done at
    sets: tuple[LoggedSet, ...]


@dataclass(frozen=True)
class BandRun:
    minutes: int
    avg_hr: int | None
    max_hr: int | None


@dataclass(frozen=True)
class CardioDetails:
    """What a cardio log said beyond its minutes (ADR-0067), each only when given."""

    effort: int | None  # session RPE 1-10
    distance_m: int | None
    pace_s_per_km: int | None  # from the minutes and distance, never stored
    avg_hr: int | None
    max_hr: int | None
    # km/h to one place, from the minutes and distance as on a proposal's card; a ride shows it
    speed_kmh: float | None = None


@dataclass(frozen=True)
class LoggedWorkout:
    workout_id: int
    name: str  # the session's, or "Extra" for an unplanned workout
    status: str  # done | rest | skipped
    planned: bool
    activity: str | None  # walk, bike...: what a cardio log was
    exercises: tuple[LoggedExercise, ...]
    band: BandRun | None  # the band's numbers, when this logs a run it recorded
    cardio: CardioDetails | None = None  # what was typed with a cardio log


def first_day(session: Session, tz: ZoneInfo) -> date:
    """The account's first day: when it was made, or the first log or tick if earlier (the
    owner's account was made by a migration, after the first workouts)."""
    user = session.get_one(User, bound_user(session))
    days = [local_date(user.created_at, tz)]
    for column in (Workout.local_date, HabitCheck.local_date):
        earliest = session.scalar(select(func.min(column)))
        if earliest is not None:
            days.append(earliest)
    return min(days)


def logged(session: Session, day: date) -> tuple[LoggedWorkout, ...]:
    """Everything logged on ``day``, in the order it was saved."""
    workouts = list(
        session.scalars(select(Workout).where(Workout.local_date == day).order_by(Workout.id))
    )
    if not workouts:
        return ()
    ids = [w.id for w in workouts]
    exercises = {e.id: e for e in session.scalars(select(Exercise))}
    steps = {step.id: step.name for step in session.scalars(select(LadderStep))}
    names = {t.id: t.name for t in session.scalars(select(SessionTemplate))}
    rows: dict[int, list[tuple[int, int, int, str, int]]] = {i: [] for i in ids}
    for log in session.scalars(
        select(SetLog).where(SetLog.workout_id.in_(ids)).order_by(SetLog.id)
    ):
        rows[log.workout_id].append(
            (log.exercise_id, log.ladder_step_id, log.set_no, log.side, log.value)
        )
    band = {
        imported.workout_id: BandRun(imported.minutes, imported.avg_hr, imported.max_hr)
        for imported in session.scalars(
            select(ImportedWorkout).where(ImportedWorkout.workout_id.in_(ids))
        )
    }
    counted = {c.workout_id: c.minutes for c in cardio_totals.logged(session, day, day)}
    grouped = {
        w.id: _as_counted(group(rows[w.id]), exercises, counted.get(w.id, {})) for w in workouts
    }
    return tuple(
        LoggedWorkout(
            workout_id=w.id,
            name=names.get(w.template_id, "Extra") if w.template_id is not None else "Extra",
            status=WorkoutStatus(w.status).value,
            planned=w.template_id is not None,
            activity=w.activity,
            exercises=tuple(
                LoggedExercise(
                    name=exercises[item.exercise_id].name,
                    unit=UNITS.get(ExerciseKind(exercises[item.exercise_id].kind), "minutes"),
                    step=steps.get(item.step_id, ""),
                    sets=item.sets,
                )
                for item in grouped[w.id]
            ),
            band=band.get(w.id),
            cardio=_details(w, _minutes(grouped[w.id], exercises)),
        )
        for w in workouts
    )


def _as_counted(
    logged: tuple[Grouped, ...], exercises: dict[int, Exercise], minutes: dict[str, int]
) -> tuple[Grouped, ...]:
    """A cardio log of one set shows the minutes it counts for, as every total does: a
    counted band workout's full minutes, though one counted before ADR-0079 logged only its
    zone 2 minutes."""
    return tuple(
        replace(e, sets=(replace(e.sets[0], left=minutes[slug]),))
        if len(e.sets) == 1 and (slug := exercises[e.exercise_id].slug) in minutes
        else e
        for e in logged
    )


def _minutes(logged: tuple[Grouped, ...], exercises: dict[int, Exercise]) -> int:
    """The minutes of a workout's timed-in-minutes exercises: its cardio."""
    return sum(
        s.left
        for e in logged
        if ExerciseKind(exercises[e.exercise_id].kind) is ExerciseKind.DURATION_MIN
        for s in e.sets
    )


def _details(workout: Workout, minutes: int) -> CardioDetails | None:
    given = (workout.effort, workout.distance_m, workout.avg_hr, workout.max_hr)
    if all(value is None for value in given):
        return None
    return CardioDetails(
        effort=workout.effort,
        distance_m=workout.distance_m,
        pace_s_per_km=pace(minutes, workout.distance_m),
        avg_hr=workout.avg_hr,
        max_hr=workout.max_hr,
        speed_kmh=round(kmh, 1) if (kmh := speed(minutes, workout.distance_m)) else None,
    )
