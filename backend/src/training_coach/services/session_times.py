"""How long guided sessions take (ADR-0061): one workout's time, and each session's usual time.

Read from the set times a guided session puts on its sets; a workout logged any other way has
none and is left out. A day run shorter (``workouts.minutes``, ADR-0082) has its own time but
doesn't count toward a session's usual, last or fastest: those are the session as planned.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from training_coach.db.models import SessionTemplate, SetLog, Workout
from training_coach.domain.session_times import SetTime, Timing, minutes, timing, usual

AS_PLANNED = Workout.minutes.is_(None)  # not run shorter for the day (ADR-0082)


@dataclass(frozen=True)
class Timed:
    workout_id: int
    template_id: int | None
    on: date
    timing: Timing


@dataclass(frozen=True)
class SessionTimes:
    """One session's times, in whole minutes: usual (ADR-0061's median), the last and fastest."""

    session: str
    usual: int
    last: int
    fastest: int
    timed: int  # how many timed sessions there are


def _timed(session: Session, *where: ColumnElement[bool]) -> list[Timed]:
    """Every timed workout matching ``where``, oldest first. Both sides of a one-sided set share
    one set's times, so each set counts once."""
    rows = session.execute(
        select(
            Workout.id,
            Workout.template_id,
            Workout.local_date,
            SetLog.exercise_id,
            SetLog.set_no,
            SetLog.started_at,
            SetLog.done_at,
        )
        .join(SetLog, SetLog.workout_id == Workout.id)
        .where(SetLog.started_at.is_not(None), SetLog.done_at.is_not(None), *where)
        .order_by(Workout.local_date, Workout.id)
    )
    found: dict[int, tuple[int | None, date, dict[tuple[int, int], SetTime]]] = {}
    for workout_id, template_id, on, exercise_id, set_no, started_at, done_at in rows:
        assert started_at is not None and done_at is not None  # noqa: S101, PT018 - filtered above
        sets = found.setdefault(workout_id, (template_id, on, {}))[2]
        sets[(exercise_id, set_no)] = SetTime(started_at, done_at)
    out = []
    for workout_id, (template_id, on, sets) in found.items():
        took = timing(sets.values())
        assert took is not None  # noqa: S101 - each has a timed set
        out.append(Timed(workout_id, template_id, on, took))
    return out


def of_workout(session: Session, workout_id: int) -> Timing | None:
    """How long a saved workout took, or None when its sets weren't timed."""
    found = _timed(session, Workout.id == workout_id)
    return found[0].timing if found else None


def usual_minutes(session: Session, template_id: int) -> int | None:
    """How long this session usually takes, in minutes; None before its first timed one."""
    found = _timed(session, Workout.template_id == template_id, AS_PLANNED)
    totals = [t.timing.total for t in found]
    typical = usual(totals)
    return minutes(typical) if typical is not None else None


def by_session(session: Session) -> list[SessionTimes]:
    """Each session with timed workouts, in plan order: its usual, last and fastest time."""
    totals: dict[int, list[timedelta]] = {}
    for timed in _timed(session, Workout.template_id.is_not(None), AS_PLANNED):
        assert timed.template_id is not None  # noqa: S101 - filtered above
        totals.setdefault(timed.template_id, []).append(timed.timing.total)
    templates = session.scalars(
        select(SessionTemplate)
        .where(SessionTemplate.id.in_(totals))
        .order_by(SessionTemplate.position, SessionTemplate.id)
    )
    out = []
    for template in templates:
        spans = totals[template.id]
        typical = usual(spans)
        assert typical is not None  # noqa: S101 - every listed session has a timed one
        out.append(
            SessionTimes(
                session=template.name,
                usual=minutes(typical),
                last=minutes(spans[-1]),
                fastest=minutes(min(spans)),
                timed=len(spans),
            )
        )
    return out
