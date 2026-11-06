"""Read-only view of the person's training plan for the dashboard (``GET /api/plan``), each
session with its home version and its gym one (ADR-0071), from their rows (ADR-0073). What an
exercise is comes from the catalogue. Progress stays out: it has its own routes.
"""

from collections.abc import Iterable
from typing import Literal, cast

from fastapi import APIRouter, Request
from pydantic import BaseModel

from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.volume import TARGET_MAX_SETS, TARGET_MIN_SETS, weekly_sets
from training_coach.services.plan_rows import PlannedItem, PlannedSession, planned_sessions
from training_coach.services.seed import ExerciseSeed, bundled_plan

router = APIRouter(prefix="/api", tags=["plan"])


class ExerciseView(BaseModel):
    slug: str
    name: str
    kind: ExerciseKind
    sets: int
    rep_min: int
    rep_max: int
    per_side: bool
    muscles: dict[str, float]  # what a set counts for each muscle (ADR-0064)
    qualities: list[str]
    pattern: str
    ladder: list[str]
    start_step: int  # the plan's starting rung, not live progress (that comes from the db)


SessionKind = Literal["strength", "conditioning", "recovery"]


class SessionView(BaseModel):
    position: int
    slug: str
    name: str
    focus: str
    type: SessionKind
    optional: bool
    total_sets: int
    exercises: list[ExerciseView]  # the home version
    gym: list[ExerciseView]  # the gym version (ADR-0071); empty: done the same way at the gym


class VolumeView(BaseModel):
    group: str
    sets: float  # fractional hard sets (ADR-0064)


class PlanView(BaseModel):
    sessions: list[SessionView]
    volume: list[VolumeView]
    volume_target_min: int
    volume_target_max: int


def _exercise_views(
    items: Iterable[PlannedItem], exercises: dict[str, ExerciseSeed]
) -> list[ExerciseView]:
    views = []
    for item in items:
        ex = exercises[item.exercise]
        views.append(
            ExerciseView(
                slug=ex.slug,
                name=ex.name,
                kind=ex.kind,
                sets=item.sets,
                rep_min=item.rep_min,
                rep_max=item.rep_max,
                per_side=item.per_side,
                muscles=dict(ex.muscles),
                qualities=list(ex.qualities),
                pattern=ex.pattern,
                ladder=list(ex.ladder),
                start_step=ex.start,
            )
        )
    return views


def build_plan_view(planned: list[PlannedSession]) -> PlanView:
    exercises = {e.slug: e for e in bundled_plan().exercises}
    sessions = [
        SessionView(
            position=session.position,
            slug=session.slug,
            name=session.name,
            focus=session.focus,
            type=cast(SessionKind, session.kind),  # the column's check holds it to these
            optional=session.optional,
            total_sets=sum(i.sets for i in session.items),
            exercises=_exercise_views(session.items, exercises),
            gym=_exercise_views(session.gym, exercises),
        )
        for session in planned
    ]
    volume = weekly_sets(
        (exercises[item.exercise].muscles, item.sets) for s in planned for item in s.items
    )
    return PlanView(
        sessions=sessions,
        volume=[VolumeView(group=g, sets=n) for g, n in volume],
        volume_target_min=TARGET_MIN_SETS,
        volume_target_max=TARGET_MAX_SETS,
    )


@router.get("/plan", response_model=PlanView)
def get_plan(request: Request, user: Owner) -> PlanView:
    """The person's training plan: the site is private (no public pages)."""
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        return build_plan_view(planned_sessions(session))
