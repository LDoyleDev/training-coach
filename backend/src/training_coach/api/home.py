"""The home screen for the web app (B1): what has been done, then today. Owner-only."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

from training_coach.api.auth import Owner
from training_coach.api.progress import ReadyView
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


class HomeWeekView(BaseModel):
    """The last 7 days, today included, the same days as ``recent`` (ADR-0077)."""

    start: date  # the first of the 7 days
    done: int
    planned: int
    extras: int
    zone2_minutes: int
    moderate_minutes: int
    zone2_target: tuple[int, int] | None


class LadderView(BaseModel):
    steps_climbed: int
    ready: list[ReadyView]  # each links to its ladder on /plan (ADR-0075)
    bests: list[str]  # personal bests in the last 7 days


class RecentView(BaseModel):
    day: date
    session: str


class HomeView(BaseModel):
    totals: TotalsView
    week: HomeWeekView
    progress: LadderView
    recent: list[RecentView]  # done in the last 7 days, newest first
    today: str | None  # today's session; empty when done or rested
    today_minutes: int | None  # about how long, from the plan; empty for a test day
    today_usual_minutes: int | None  # how long it usually takes, once timed (ADR-0061)


@router.get("", response_model=HomeView)
def home(request: Request, user: Owner) -> HomeView:
    """All-time totals, the last 7 days against the plan, ladder progress, what was done on
    each of those days and today's session."""
    settings: Settings = request.app.state.settings
    on = local_date(datetime.now(UTC), settings.tz)
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        found = service.home(session, on, settings.tz)
    return HomeView(
        totals=TotalsView(**vars(found.totals)),
        week=HomeWeekView(**vars(found.week)),
        progress=LadderView(
            steps_climbed=found.progress.steps_climbed,
            ready=[ReadyView(exercise=r.exercise, slug=r.slug) for r in found.progress.ready],
            bests=found.progress.bests,
        ),
        recent=[RecentView(day=r.day, session=r.session) for r in found.recent],
        today=found.today,
        today_minutes=found.today_minutes,
        today_usual_minutes=found.today_usual_minutes,
    )
