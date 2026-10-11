"""The home screen (B1 in docs/specs/ux-flow-plan.md): what has been done, then today.

All-time totals to motivate, this week against the plan (the weekly review's numbers, reused),
progress on the ladders, the last seven days, and today's session for the button. It only
reads; the caller owns the session.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, Exercise, SessionTemplate, SetLog, Workout
from training_coach.domain.enums import ExerciseKind, WorkoutStatus
from training_coach.services import guided, retests, review

MOVED_UP = "progress.moved_up"  # written by progress.move_up
RECENT_DAYS = 7


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
    start: date  # Monday
    done: int  # planned sessions done
    planned: int  # sessions in the plan's cycle
    extras: int
    zone2_minutes: int
    zone2_target: tuple[int, int] | None


@dataclass(frozen=True)
class Ladder:
    steps_climbed: int  # ladder steps moved up so far
    ready: list[str]  # exercises ready to move up now
    bests: list[str]  # exercises with a personal best this week


@dataclass(frozen=True)
class Recent:
    day: date
    session: str  # the planned session's name, or "Extra"


@dataclass(frozen=True)
class Home:
    totals: Totals
    week: Week
    progress: Ladder
    recent: list[Recent]  # done in the last seven days, newest first
    today: str | None  # today's session (or a test day due today); None when done or rested


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
    since = on - timedelta(days=RECENT_DAYS - 1)
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
    return [Recent(w.local_date, _label(w, names)) for w in workouts]


def _label(workout: Workout, names: dict[int, str]) -> str:
    """The session's name; a cardio log adds what it was: "Long zone 2: hike, 62 min", or
    "Walk, 30 min" for an extra. Anything else unplanned is "Extra"."""
    name = names.get(workout.template_id) if workout.template_id is not None else None
    if workout.activity is None:
        return name or "Extra"
    detail = f"{workout.activity}, {sum(s.value for s in workout.sets)} min"
    return f"{name}: {detail}" if name else detail.capitalize()


def _today(session: Session, on: date, tz: ZoneInfo) -> str | None:
    test_day = retests.due(session, on, tz)
    if test_day is not None:
        return test_day.name
    plan = guided.today(session, on, tz)
    return plan.name if plan is not None else None


def home(session: Session, on: date, tz: ZoneInfo) -> Home:
    """The home screen for local day ``on``."""
    weekly = review.weekly(session, on, tz)
    climbed = session.scalar(select(func.count()).select_from(Event).where(Event.kind == MOVED_UP))
    return Home(
        totals=_totals(session, on),
        week=Week(
            start=weekly.start,
            done=weekly.done,
            planned=weekly.planned,
            extras=weekly.extras,
            zone2_minutes=weekly.zone2_minutes,
            zone2_target=weekly.zone2_target,
        ),
        progress=Ladder(
            steps_climbed=climbed or 0,
            ready=list(weekly.ready),
            bests=list(dict.fromkeys(b.exercise for b in weekly.bests)),
        ),
        recent=_recent(session, on),
        today=_today(session, on, tz),
    )
