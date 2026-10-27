"""The home screen (B1 in docs/specs/ux-flow-plan.md): what has been done, then today.

All-time totals to motivate, the last 7 days against the plan (counted as the weekly review
counts, over today and the six days before, ADR-0077), progress on the ladders, what was done
on each of those days, and today's session for the button. It only reads; the caller owns the
session.
"""

from dataclasses import dataclass, field
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, Exercise, SessionTemplate, SetLog, Workout
from training_coach.domain.enums import ExerciseKind, WorkoutStatus
from training_coach.domain.zones import Split
from training_coach.services import (
    cardio_totals,
    guided,
    progress,
    retests,
    review,
    session_times,
)
from training_coach.services.progress import Ready

MOVED_UP = "progress.moved_up"  # written by progress.move_up


@dataclass(frozen=True)
class Totals:
    sessions: int  # done workouts, planned or extra
    sets: int  # a set done on both sides (left and right) counts once, as the review does
    reps: int  # every rep logged on a reps exercise, both sides of a one-sided set added
    cardio_minutes: int  # zone 2 and moderate cardio
    first_day: date | None  # the first done workout
    days: int  # days since first_day (0 on the first day, or with nothing done)


@dataclass(frozen=True)
class Week:
    """The last 7 days, the same days as ``Home.recent`` (ADR-0077)."""

    start: date  # the first of the 7 days
    done: int  # planned sessions done
    planned: int  # sessions in the plan's cycle
    extras: int
    zone2_minutes: int
    moderate_minutes: int
    zone2_target: tuple[int, int] | None
    cardio: Split = field(default_factory=Split)  # all cardio minutes by zone (ADR-0079)
    cardio_target: tuple[int, int] | None = None


@dataclass(frozen=True)
class Ladder:
    steps_climbed: int  # ladder steps moved up so far
    ready: list[Ready]  # exercises ready to move up now
    bests: list[str]  # exercises with a personal best in the last 7 days


@dataclass(frozen=True)
class Recent:
    day: date
    session: str  # the planned session's name, or "Extra"


@dataclass(frozen=True)
class Home:
    totals: Totals
    week: Week
    progress: Ladder
    recent: list[Recent]  # done in the last 7 days, newest first
    today: str | None  # today's session (or a test day due today); None when done or rested
    today_minutes: int | None  # about how long, from the plan; None for a test day
    today_usual_minutes: int | None  # how long it usually takes, once timed (ADR-0061)


def _totals(session: Session, on: date) -> Totals:
    done = Workout.status == WorkoutStatus.DONE
    sessions = session.scalar(select(func.count()).select_from(Workout).where(done)) or 0
    first = session.scalar(select(func.min(Workout.local_date)).where(done))
    one_per_set = (
        select(SetLog.workout_id, SetLog.exercise_id, SetLog.set_no)
        .join(Workout)
        .where(done)
        .distinct()
        .subquery()
    )
    sets = session.scalar(select(func.count()).select_from(one_per_set)) or 0
    reps = session.scalar(
        select(func.sum(SetLog.value))
        .join(Workout)
        .join(Exercise, Exercise.id == SetLog.exercise_id)
        .where(done, Exercise.kind == ExerciseKind.REPS)
    )
    minutes = review.cardio_minutes(session, first, on) if first is not None else {}
    return Totals(
        sessions=sessions,
        sets=sets,
        reps=int(reps or 0),
        cardio_minutes=sum(minutes.values()),
        first_day=first,
        days=max((on - first).days, 0) if first is not None else 0,
    )


def _recent(session: Session, on: date) -> list[Recent]:
    since = review.last_days(on)
    names = {t.id: t.name for t in session.scalars(select(SessionTemplate))}
    workouts = session.scalars(
        select(Workout)
        .where(
            Workout.status == WorkoutStatus.DONE,
            Workout.local_date >= since,
            Workout.local_date <= on,
        )
        .order_by(Workout.local_date.desc(), Workout.created_at.desc(), Workout.id.desc())
    )
    minutes = {c.workout_id: c.total for c in cardio_totals.logged(session, since, on)}
    return [Recent(w.local_date, _label(w, names, minutes)) for w in workouts]


def _label(workout: Workout, names: dict[int, str], minutes: dict[int, int]) -> str:
    """The session's name; a cardio log adds what it was: "Long zone 2: hike, 62 min", or
    "Walk, 30 min" for an extra, a counted band workout for all its minutes (ADR-0079).
    Anything else unplanned is "Extra"."""
    name = names.get(workout.template_id) if workout.template_id is not None else None
    if workout.activity is None:
        return name or "Extra"
    total = minutes.get(workout.id, sum(s.value for s in workout.sets))
    detail = f"{workout.activity}, {total} min"
    return f"{name}: {detail}" if name else detail.capitalize()


def _today(session: Session, on: date, tz: ZoneInfo) -> tuple[str | None, int | None, int | None]:
    """Today's session for the button: its name, the plan's minutes and the usual minutes."""
    test_day = retests.due(session, on, tz)
    if test_day is not None:
        return test_day.name, None, None
    plan = guided.today(session, on, tz)
    if plan is None:
        return None, None, None
    if plan.after_run:  # the rest of the day's session after its cardio (ADR-0066)
        return f"{plan.name}, after your run", plan.minutes, None
    return plan.name, plan.minutes, session_times.usual_minutes(session, plan.template_id)


def home(session: Session, on: date, tz: ZoneInfo) -> Home:
    """The home screen for local day ``on``."""
    today, minutes, usual = _today(session, on, tz)
    start = review.last_days(on)
    span = review.span(session, start, on)
    targets = cardio_totals.targets(session)
    climbed = session.scalar(select(func.count()).select_from(Event).where(Event.kind == MOVED_UP))
    return Home(
        totals=_totals(session, on),
        week=Week(
            start=start,
            done=span.done,
            planned=review.planned_sessions(session),
            extras=span.extras,
            zone2_minutes=span.zone2_minutes,
            moderate_minutes=span.moderate_minutes,
            zone2_target=targets.zone2,
            cardio=span.cardio,
            cardio_target=targets.total,
        ),
        progress=Ladder(
            steps_climbed=climbed or 0,
            ready=progress.ready(progress.overview(session)),
            bests=list(dict.fromkeys(b.exercise for b in span.bests)),
        ),
        recent=_recent(session, on),
        today=today,
        today_minutes=minutes,
        today_usual_minutes=usual,
    )
