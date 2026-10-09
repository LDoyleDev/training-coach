"""Today's guided session for the web app (D1, #117). Owner-only."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.queue import local_date
from training_coach.services import guided

router = APIRouter(prefix="/api/session", tags=["session"])

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


class TodayView(BaseModel):
    """``session`` is empty when nothing planned is left today (done or rested)."""

    session: GuidedView | None


@router.get("/today", response_model=TodayView)
def today(
    request: Request,
    user: Owner,
    first: Annotated[list[int], Query(max_length=10)] = [],  # noqa: B006 - FastAPI query default
) -> TodayView:
    """Today's session in work order. ``first`` names pairs to start with their second
    exercise ("Do this one first")."""
    settings: Settings = request.app.state.settings
    on = local_date(datetime.now(UTC), settings.tz)
    sessions = make_session_factory(request.app.state.engine, user_id=user)
    with session_scope(sessions) as session:
        plan = guided.today(session, on, settings.tz, set(first))
    if plan is None:
        return TodayView(session=None)
    return TodayView(
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
        )
    )
