"""The easy start's two offers on Today (ADR-0094): "One more easy week" and "Start the easy
start again". Each answers Today as it is then; 409 when it isn't on offer. Owner-only."""

from collections.abc import Callable
from datetime import UTC, date, datetime

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.orm import Session

from training_coach.api.auth import Owner
from training_coach.api.session import TodayView, today_view
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import easy_start

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/easy-start", tags=["easy-start"])


def _offer(request: Request, user: int, take: Callable[[Session, date], str | None]) -> TodayView:
    settings: Settings = request.app.state.settings
    on = local_date(datetime.now(UTC), settings.tz)
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        problem = take(session, on)
        if problem is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, problem)
        log.info("api.easy_start", took=take.__name__)
        return today_view(session, on, settings)


@router.post("/extend", response_model=TodayView)
def post_extend(request: Request, user: Owner) -> TodayView:
    """ "One more easy week": 7 more days of the phase that just ended, at most twice."""
    return _offer(request, user, easy_start.extend)


@router.post("/restart", response_model=TodayView)
def post_restart(request: Request, user: Owner) -> TodayView:
    """ "Start the easy start again" after 14 days or more without a workout."""
    return _offer(request, user, easy_start.restart)
