"""The home screen for the web app (B1): what has been done, then today. Owner-only."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import home as service

router = APIRouter(prefix="/api/home", tags=["home"])


class TotalsView(BaseModel):
    sessions: int
    sets: int  # a set done on both sides counts once
    reps: int  # both sides of a one-sided set are added
    cardio_minutes: int
    first_day: date | None
    days: int  # since the first done workout


class WeekView(BaseModel):
    start: date  # Monday
    done: int
    planned: int
    extras: int
    zone2_minutes: int
    zone2_target: tuple[int, int] | None


class LadderView(BaseModel):
    steps_climbed: int
    ready: list[str]
    bests: list[str]  # personal bests this week


class RecentView(BaseModel):
    day: date
    session: str


class HomeView(BaseModel):
    totals: TotalsView
    week: WeekView
    progress: LadderView
    recent: list[RecentView]  # done in the last seven days, newest first
    today: str | None  # today's session; empty when done or rested


@router.get("", response_model=HomeView)
def home(request: Request, user: Owner) -> HomeView:
    """All-time totals, this week against the plan, ladder progress, the last seven days and
    today's session."""
    settings: Settings = request.app.state.settings
    on = local_date(datetime.now(UTC), settings.tz)
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        found = service.home(session, on, settings.tz)
    return HomeView(
        totals=TotalsView(**vars(found.totals)),
        week=WeekView(**vars(found.week)),
        progress=LadderView(**vars(found.progress)),
        recent=[RecentView(day=r.day, session=r.session) for r in found.recent],
        today=found.today,
    )
