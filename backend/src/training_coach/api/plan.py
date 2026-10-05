"""Read-only view of the training plan for the dashboard (``GET /api/plan``).

Public by design: the plan holds no personal data (no measurements, photos or logs), so it is
safe to show through the share-visible dashboard (ADR-0012).
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from training_coach.domain.enums import ExerciseKind
from training_coach.domain.volume import TARGET_MAX_SETS, TARGET_MIN_SETS, weekly_sets
from training_coach.services.seed import bundled_plan

router = APIRouter(prefix="/api", tags=["plan"])


class ExerciseView(BaseModel):
    slug: str
    name: str
    kind: ExerciseKind
    sets: int
    rep_min: int
    rep_max: int
    per_side: bool
    muscle_groups: list[str]
    ladder: list[str]
    current_step: int


class SessionView(BaseModel):
    position: int
    slug: str
    name: str
    focus: str
    type: Literal["strength", "conditioning", "recovery"]
    optional: bool
    total_sets: int
    exercises: list[ExerciseView]


class VolumeView(BaseModel):
    group: str
    sets: int


class PlanView(BaseModel):
    sessions: list[SessionView]
    volume: list[VolumeView]
    volume_target_min: int
    volume_target_max: int


def build_plan_view() -> PlanView:
    plan = bundled_plan()
    exercises = {e.slug: e for e in plan.exercises}
    sessions: list[SessionView] = []
    for position, session in enumerate(plan.sessions):
        views = []
        for item in session.items:
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
                    muscle_groups=list(ex.muscle_groups),
                    ladder=list(ex.ladder),
                    current_step=ex.start,
                )
            )
        sessions.append(
            SessionView(
                position=position,
                slug=session.slug,
                name=session.name,
                focus=session.focus,
                type=session.type,
                optional=session.is_rest_optional,
                total_sets=sum(i.sets for i in session.items),
                exercises=views,
            )
        )
    volume = weekly_sets(
        (exercises[item.exercise].muscle_groups, item.sets)
        for session in plan.sessions
        for item in session.items
    )
    return PlanView(
        sessions=sessions,
        volume=[VolumeView(group=g, sets=n) for g, n in volume],
        volume_target_min=TARGET_MIN_SETS,
        volume_target_max=TARGET_MAX_SETS,
    )


@router.get("/plan", response_model=PlanView)
async def get_plan() -> PlanView:
    return build_plan_view()
