"""A day's log for Today (ADR-0068): what was saved on a day, today or earlier, read-only.
Owner-only. "Today" is the local day in ``settings.tz``; a later day is refused, and so is a
day before the account's first."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import day_view

router = APIRouter(prefix="/api/day", tags=["day"])

LATER = "that day hasn't happened yet"
EARLIER = "that's before your first day in the coach"


class LoggedSetView(BaseModel):
    set_no: int
    left: int
    right: int | None  # a one-sided set's right side; empty otherwise


class LoggedExerciseView(BaseModel):
    name: str
    unit: str  # reps | seconds | minutes
    step: str
    sets: list[LoggedSetView]


class BandRunView(BaseModel):
    minutes: int
    avg_hr: int | None
    max_hr: int | None


class CardioDetailsView(BaseModel):
    effort: int | None
    distance_m: int | None
    pace_s_per_km: int | None
    avg_hr: int | None
    max_hr: int | None
    speed_kmh: float | None  # from the minutes and distance, to one place: a ride shows it


class LoggedWorkoutView(BaseModel):
    workout_id: int
    name: str
    status: str  # done | rest | skipped
    planned: bool
    activity: str | None
    exercises: list[LoggedExerciseView]
    band: BandRunView | None
    cardio: CardioDetailsView | None  # effort, distance, pace and heart rate typed with it


class DayView(BaseModel):
    day: date
    today: date  # the server's today: the newest day to show
    first: date  # the account's first day: the oldest
    workouts: list[LoggedWorkoutView]


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


@router.get("", response_model=DayView)
def get_day(request: Request, user: Owner, on: date | None = None) -> DayView:
    """What was logged on ``on`` (default: today)."""
    settings: Settings = request.app.state.settings
    today = local_date(datetime.now(UTC), settings.tz)
    day = on or today
    if day > today:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, LATER)
    with session_scope(_bound(request, user)) as session:
        first = day_view.first_day(session, settings.tz)
        if day < first:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, EARLIER)
        found = day_view.logged(session, day)
        return DayView(
            day=day,
            today=today,
            first=first,
            workouts=[
                LoggedWorkoutView(
                    workout_id=w.workout_id,
                    name=w.name,
                    status=w.status,
                    planned=w.planned,
                    activity=w.activity,
                    exercises=[
                        LoggedExerciseView(
                            name=e.name,
                            unit=e.unit,
                            step=e.step,
                            sets=[LoggedSetView(**vars(s)) for s in e.sets],
                        )
                        for e in w.exercises
                    ],
                    band=BandRunView(**vars(w.band)) if w.band is not None else None,
                    cardio=CardioDetailsView(**vars(w.cardio)) if w.cardio is not None else None,
                )
                for w in found
            ],
        )
