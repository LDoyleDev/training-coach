"""Each exercise's standing for the web Progress page, as /progress in the bot, and how long each
session takes (ADR-0061). Owner-only."""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.api.session import UNITS
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import progress, session_times

router = APIRouter(prefix="/api/progress", tags=["progress"])


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


class PointView(BaseModel):
    day: date
    best: int  # the session's best set
    step_number: int  # a change from the point before is a move up


class StandingView(BaseModel):
    exercise: str
    unit: Literal["reps", "seconds", "minutes"]
    step: str
    step_number: int
    steps: int
    last: list[int]  # the latest session at this step, per set; empty if none yet
    best_set: int | None
    status: Literal["hold", "ready", "top_of_ladder"]
    retired: bool
    trend: list[PointView]  # the last six weeks, oldest first, across ladder steps


class StandingsView(BaseModel):
    today: date  # the trends' last day, so the graphs use the server's window, not the device's
    standings: list[StandingView]


@router.get("", response_model=StandingsView)
def standings(request: Request, user: Owner) -> StandingsView:
    """Every exercise in plan order: its step, last session, best set and whether it's ready."""
    settings: Settings = request.app.state.settings
    on = local_date(datetime.now(UTC), settings.tz)
    with session_scope(_bound(request, user)) as session:
        found = progress.overview(session, on)
    return StandingsView(
        today=on,
        standings=[
            StandingView(
                exercise=s.exercise,
                unit=UNITS[s.kind],
                step=s.step,
                step_number=s.step_number,
                steps=s.steps,
                last=list(s.last),
                best_set=s.best_set,
                status=s.status.value,
                retired=s.retired,
                trend=[
                    PointView(day=p.day, best=p.best, step_number=p.step_number) for p in s.trend
                ],
            )
            for s in found
        ],
    )


class SessionTimeView(BaseModel):
    """A session's times in whole minutes, from its timed guided sessions (ADR-0061)."""

    session: str
    usual: int  # the median of the last five
    last: int
    fastest: int
    timed: int  # how many were timed


@router.get("/times", response_model=list[SessionTimeView])
def times(request: Request, user: Owner) -> list[SessionTimeView]:
    """Each session that has been timed, in plan order: how long it usually takes."""
    with session_scope(_bound(request, user)) as session:
        found = session_times.by_session(session)
    return [
        SessionTimeView(
            session=t.session, usual=t.usual, last=t.last, fastest=t.fastest, timed=t.timed
        )
        for t in found
    ]
