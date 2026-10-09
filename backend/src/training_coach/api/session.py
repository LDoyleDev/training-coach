"""Today's guided session for the web app (D1, #117). Owner-only."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.queue import local_date
from training_coach.services import guided, stretching, workout_log
from training_coach.services import progress as feedback

router = APIRouter(prefix="/api/session", tags=["session"])


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _settings_and_day(request: Request) -> tuple[Settings, date]:
    settings: Settings = request.app.state.settings
    return settings, local_date(datetime.now(UTC), settings.tz)


UNITS: dict[ExerciseKind, Literal["reps", "seconds", "minutes"]] = {
    ExerciseKind.REPS: "reps",
    ExerciseKind.SECONDS: "seconds",
    ExerciseKind.DURATION_MIN: "minutes",
}


class ItemView(BaseModel):
    slug: str
    name: str
    step: str
    summary: str | None
    cue: str | None
    unit: Literal["reps", "seconds", "minutes"]
    per_side: bool
    pair: int | None
    targets: list[int]


class SetView(BaseModel):
    item: int  # index into items
    set_no: int
    target: int


class BlockView(BaseModel):
    kind: Literal["strength", "hypertrophy"]
    week: int


class GuidedView(BaseModel):
    day: str  # ISO date, local
    template_id: int
    name: str
    focus: str
    kind: Literal["strength", "conditioning", "recovery"]
    warm_up: bool
    block: BlockView | None
    minutes: int
    rest_seconds: int
    items: list[ItemView]
    order: list[SetView]


class DoneView(BaseModel):
    """A confirmed set; ``right`` only for one-sided exercises (empty: same as left)."""

    item: int = Field(ge=0, le=100)
    set_no: int = Field(ge=1, le=50)
    left: int = Field(ge=0, le=3600)
    right: int | None = Field(default=None, ge=0, le=3600)


class ProgressView(BaseModel):
    template_id: int
    position: int
    first: list[int]
    sets: list[DoneView]
    saved: bool


class TodayView(BaseModel):
    """``session`` is empty when nothing planned is left today (done or rested); ``progress``
    is where the person left off, to resume."""

    session: GuidedView | None
    progress: ProgressView | None = None


class KeepBody(BaseModel):
    template_id: int  # the session the browser shows: a different one now is a conflict
    position: int = Field(ge=0, le=500)
    first: list[int] = Field(default_factory=list, max_length=10)
    sets: list[DoneView] = Field(default_factory=list, max_length=200)


class SaveBody(BaseModel):
    day: date | None = None  # empty: today; an earlier day saves one left unsaved


class EarnedView(BaseModel):
    exercise: str
    unit: Literal["reps", "seconds", "minutes"]
    best_set: int | None
    total: int | None
    next_step: str | None  # ready to move up to this


class SavedView(BaseModel):
    workout_id: int
    already_saved: bool
    next_session: str | None
    earned: list[EarnedView]
    stretching: bool  # offered after a resistance session (ADR-0032)


class PendingView(BaseModel):
    day: date
    session: str
    sets: int


@router.get("/today", response_model=TodayView)
def today(
    request: Request,
    user: Owner,
    first: Annotated[list[int], Query(max_length=10)] = [],  # noqa: B006 - FastAPI query default
) -> TodayView:
    """Today's session in work order. ``first`` names pairs to start with their second
    exercise ("Do this one first")."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        kept = guided.kept(session, on)
        swapped = set(first) if first else set(kept.first if kept is not None else ())
        plan = guided.today(session, on, settings.tz, swapped)
    if plan is None:
        return TodayView(session=None)
    progress = None
    if kept is not None and kept.template_id == plan.template_id:
        progress = ProgressView(
            template_id=kept.template_id,
            position=kept.position,
            first=list(kept.first),
            sets=[DoneView(**vars(d)) for d in kept.sets],
            saved=kept.saved,
        )
    return TodayView(
        progress=progress,
        session=GuidedView(
            day=plan.day.isoformat(),
            template_id=plan.template_id,
            name=plan.name,
            focus=plan.focus,
            kind=plan.kind,
            warm_up=plan.warm_up,
            block=BlockView(kind=plan.block.kind.value, week=plan.block.week)
            if plan.block is not None
            else None,
            minutes=plan.minutes,
            rest_seconds=plan.rest_seconds,
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
                )
                for i in plan.items
            ],
            order=[SetView(item=s.item, set_no=s.set_no, target=s.target) for s in plan.order],
        ),
    )


@router.put("/progress", status_code=status.HTTP_204_NO_CONTENT)
def keep(body: KeepBody, request: Request, user: Owner) -> None:
    """Keep where the person is in today's session, so it resumes on any device."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        plan = guided.today(session, on, settings.tz, set(body.first))
        if plan is None or plan.template_id != body.template_id:
            raise HTTPException(status.HTTP_409_CONFLICT, "today's session has changed")
        sets = [guided.Done(**d.model_dump()) for d in body.sets]
        problem = guided.keep(session, plan, body.position, body.first, sets)
    if problem is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)


@router.post("/save", response_model=SavedView)
def save(body: SaveBody, request: Request, user: Owner) -> SavedView:
    """Save the guided session as a workout: today's, or an earlier day's left unsaved."""
    settings, today = _settings_and_day(request)
    day = body.day or today
    if day > today:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "that day hasn't happened yet")
    with session_scope(_bound(request, user)) as session:
        result = guided.save(session, day, today, settings.tz)
        if isinstance(result, str):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, result)
        if isinstance(result, workout_log.Stale):
            raise HTTPException(status.HTTP_409_CONFLICT, "today's session has changed")
        earned = (
            []
            if result.already_saved
            else feedback.feedback(session, result.workout_id, settings.tz)
        )
        return SavedView(
            workout_id=result.workout_id,
            already_saved=result.already_saved,
            next_session=workout_log.next_session_name(session),
            earned=[
                EarnedView(
                    exercise=e.exercise,
                    unit=UNITS[e.kind],
                    best_set=e.bests.best_set,
                    total=e.bests.total,
                    next_step=e.next_step,
                )
                for e in earned
                if e.bests or e.next_step
            ],
            stretching=day == today and stretching.offered(session, result.workout_id),
        )


@router.get("/pending", response_model=list[PendingView])
def pending(request: Request, user: Owner) -> list[PendingView]:
    """Earlier days' guided sessions with sets but never saved, to offer saving them."""
    _, today = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        return [
            PendingView(day=p.day, session=p.session, sets=p.sets)
            for p in guided.pending(session, today)
        ]
