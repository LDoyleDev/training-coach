"""Logging cardio in one step from the web (ux-flow-plan A1-A3). Owner-only."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import CardioActivity
from training_coach.domain.queue import local_date
from training_coach.services import cardio, workout_log

router = APIRouter(prefix="/api/cardio", tags=["cardio"])

Kind = Literal["zone2", "moderate-cardio", "hiit"]


class PlannedView(BaseModel):
    kind: Kind
    session: str
    target: int  # minutes, or rounds for HIIT


class WeekView(BaseModel):
    zone2: int
    moderate: int
    zone2_target: list[int] | None  # [low, high] minutes


class OptionsView(BaseModel):
    """``planned`` is today's session when it is a single cardio exercise: "Done as planned"
    saves its target in one tap. Any other cardio is logged as an extra."""

    planned: PlannedView | None
    activities: list[CardioActivity]
    week: WeekView


class LogBody(BaseModel):
    token: str = Field(pattern="^[0-9a-f]{32}$")  # one per log: a repeated save changes nothing
    kind: Kind
    value: int = Field(ge=1, le=cardio.MAX_MINUTES)  # minutes, or rounds for HIIT
    activity: CardioActivity | None = None


class LoggedView(BaseModel):
    workout_id: int
    already_saved: bool
    planned: bool  # it completed today's planned session
    next_session: str | None
    week: WeekView


def _week(found: cardio.Week) -> WeekView:
    target = list(found.zone2_target) if found.zone2_target is not None else None
    return WeekView(zone2=found.zone2, moderate=found.moderate, zone2_target=target)


@router.get("", response_model=OptionsView)
def options(request: Request, user: Owner) -> OptionsView:
    settings = request.app.state.settings
    on = local_date(datetime.now(UTC), settings.tz)
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        planned = cardio.planned(session, on, settings.tz)
        week = cardio.week(session, on)
    return OptionsView(
        planned=PlannedView.model_validate(vars(planned)) if planned is not None else None,
        activities=list(CardioActivity),
        week=_week(week),
    )


@router.post("", response_model=LoggedView)
def log(body: LogBody, request: Request, user: Owner) -> LoggedView:
    """Save one cardio log for today. 409 when today's session changed meanwhile."""
    if (problem := cardio.problem(body.kind, body.value)) is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    settings = request.app.state.settings
    on = local_date(datetime.now(UTC), settings.tz)
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        result = cardio.log(
            session, on, settings.tz, body.kind, body.value, body.activity, body.token
        )
        if isinstance(result, workout_log.Stale):
            raise HTTPException(status.HTTP_409_CONFLICT, "today's session has changed")
        return LoggedView(
            workout_id=result.saved.workout_id,
            already_saved=result.saved.already_saved,
            planned=result.planned,
            next_session=workout_log.next_session_name(session),
            week=_week(cardio.week(session, on)),
        )
