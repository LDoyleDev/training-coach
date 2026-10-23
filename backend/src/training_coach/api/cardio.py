"""Logging cardio in one step from the web (ux-flow-plan A1-A3). Owner-only."""

from datetime import UTC, datetime, time
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from training_coach.api.auth import Owner
from training_coach.api.clash import CLASH, ClashReply, conflict, resolution
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain import cardio as details
from training_coach.domain.enums import CardioActivity
from training_coach.domain.queue import local_date
from training_coach.services import cardio, workout_log
from training_coach.services.day_clash import Clash, Refused

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


class LogBody(ClashReply):
    token: str = Field(pattern="^[0-9a-f]{32}$")  # one per log: a repeated save changes nothing
    kind: Kind
    value: int = Field(ge=1, le=cardio.MAX_MINUTES)  # minutes, or rounds for HIIT
    activity: CardioActivity | None = None
    # Each only when given (ADR-0067): how hard it felt (session RPE), the distance, heart rate
    # and the local time it started. Bounds beyond these are checked by the domain.
    effort: int | None = Field(default=None, ge=1, le=10)
    distance_km: float | None = Field(default=None, gt=0, le=300)
    avg_hr: int | None = Field(default=None, ge=30, le=230)
    max_hr: int | None = Field(default=None, ge=30, le=230)
    start: time | None = None  # local clock time today, e.g. "16:26"


class LoggedView(BaseModel):
    workout_id: int
    already_saved: bool
    planned: bool  # it completed today's planned session
    pace: int | None = None  # seconds per km, from minutes and distance
    next_session: str | None
    week: WeekView


def week_view(found: cardio.Week) -> WeekView:
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
        week=week_view(week),
    )


@router.post("", response_model=LoggedView, responses=CLASH)
def log(body: LogBody, request: Request, user: Owner) -> LoggedView:
    """Save one cardio log for today. 409 when today's session changed meanwhile, or with
    what is saved already when the day has its session (ADR-0060)."""
    settings = request.app.state.settings
    now = datetime.now(UTC)
    on = local_date(now, settings.tz)
    started = cardio.started(on, body.start, settings.tz, now) if body.start else None
    if body.start and started is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "the start is still to come")
    found = details.Details(
        effort=body.effort,
        distance_m=round(body.distance_km * 1000) if body.distance_km is not None else None,
        avg_hr=body.avg_hr,
        max_hr=body.max_hr,
        started_at=started,
    )
    if (problem := cardio.problem(body.kind, body.value, found)) is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        result = cardio.log(
            session,
            on,
            settings.tz,
            body.kind,
            body.value,
            body.activity,
            body.token,
            answer=resolution(body),
            details=found,
        )
        if isinstance(result, Clash | Refused):
            raise conflict(result)
        if isinstance(result, workout_log.Stale):
            raise HTTPException(status.HTTP_409_CONFLICT, "today's session has changed")
        return LoggedView(
            workout_id=result.saved.workout_id,
            already_saved=result.saved.already_saved,
            planned=result.planned,
            pace=details.pace(body.value, found.distance_m),
            next_session=workout_log.next_session_name(session),
            week=week_view(cardio.week(session, on)),
        )
