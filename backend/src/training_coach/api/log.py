"""Logging any day from the web (ADR-0060): today back to 14 days, any session, an extra,
cardio or an earlier rest day. Owner-only.

A save for a day that already has its session answers 409 with what is there; the browser
asks and sends the same save again with the answer (``api.clash``).
"""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.api.clash import CLASH, ClashReply, conflict, resolution
from training_coach.api.session import UNITS, DoneView, ItemView
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.dates import day_problem
from training_coach.domain.enums import CardioActivity
from training_coach.domain.queue import local_date
from training_coach.services import day_log, guided, workout_log
from training_coach.services.day_clash import Clash, Refused

router = APIRouter(prefix="/api/log", tags=["log"])


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _settings_and_day(request: Request) -> tuple[Settings, date]:
    settings: Settings = request.app.state.settings
    return settings, local_date(datetime.now(UTC), settings.tz)


class LogChoiceView(BaseModel):
    template_id: int
    name: str
    kind: Literal["strength", "conditioning", "recovery"]


class LogOptionsView(BaseModel):
    """What a log can be: every session, and what cardio was. The days are today back to 14
    days ago (``domain.dates.MAX_DAYS_BACK``); the browser lists them, the save checks them."""

    sessions: list[LogChoiceView]
    activities: list[CardioActivity]


class LogPlanView(BaseModel):
    day: date
    template_id: int
    name: str
    items: list[ItemView]  # in plan order, with that day's targets


class LogDayBody(ClashReply):
    token: str = Field(pattern="^[0-9a-f]{32}$")  # one per log: a repeated save changes nothing
    day: date
    what: Literal["session", "extra", "rest", "cardio"]
    template_id: int | None = None  # session and extra: whose exercises
    sets: list[DoneView] = Field(default_factory=list, max_length=200)
    cardio: Literal["zone2", "moderate-cardio", "hiit"] | None = None
    value: int | None = Field(default=None, ge=1, le=600)  # minutes, or rounds for HIIT
    activity: CardioActivity | None = None


class LoggedDayView(BaseModel):
    workout_id: int
    already_saved: bool
    next_session: str | None


@router.get("", response_model=LogOptionsView)
def options(request: Request, user: Owner) -> LogOptionsView:
    with session_scope(_bound(request, user)) as session:
        found = day_log.choices(session)
    return LogOptionsView(
        sessions=[LogChoiceView.model_validate(vars(c)) for c in found],
        activities=list(CardioActivity),
    )


@router.get("/plan", response_model=LogPlanView)
def plan(day: date, template_id: int, request: Request, user: Owner) -> LogPlanView:
    """A session's exercises and targets, to enter what was done on ``day``."""
    settings, today = _settings_and_day(request)
    if (problem := day_problem(day, today)) is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    with session_scope(_bound(request, user)) as session:
        found = day_log.plan(session, day, template_id, settings.tz)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, day_log.NO_SESSION)
    return LogPlanView(
        day=day,
        template_id=found.template_id,
        name=found.name,
        items=[
            ItemView(
                slug=i.slug,
                name=i.exercise,
                step=i.step,
                summary=i.summary,
                cue=i.cue,
                unit=UNITS[i.kind],
                per_side=i.per_side,
                pair=i.pair,
                targets=list(i.targets),
                baseline=i.baseline,
            )
            for i in found.items
        ],
    )


@router.post("", response_model=LoggedDayView, responses=CLASH)
def log(body: LogDayBody, request: Request, user: Owner) -> LoggedDayView:
    """Save what was done on a day. 409 with what is there when the day already has its
    session; 422 with the reason when it can't be saved."""
    settings, today = _settings_and_day(request)
    answer = resolution(body)
    with session_scope(_bound(request, user)) as session:
        result: day_log.Saving
        if body.what == "rest":
            result = day_log.save_rest(session, body.day, today, settings.tz, body.token, answer)
        elif body.what == "cardio":
            if body.cardio is None or body.value is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "cardio needs a value")
            result = day_log.save_cardio(
                session,
                body.day,
                today,
                settings.tz,
                body.cardio,
                body.value,
                body.activity,
                body.token,
                answer,
            )
        else:
            if body.template_id is None:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, day_log.NO_SESSION)
            result = day_log.save_sets(
                session,
                body.day,
                today,
                settings.tz,
                body.template_id,
                # A day logged afterwards has no set times (ADR-0061).
                [guided.Done(**d.model_dump(exclude={"started_at", "done_at"})) for d in body.sets],
                body.token,
                extra=body.what == "extra",
                answer=answer,
            )
        if isinstance(result, Clash | Refused):
            raise conflict(result)
        if isinstance(result, str):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, result)
        if isinstance(result, workout_log.Stale):
            raise HTTPException(status.HTTP_409_CONFLICT, "the plan has changed: reload")
        return LoggedDayView(
            workout_id=result.workout_id,
            already_saved=result.already_saved,
            next_session=workout_log.next_session_name(session),
        )
