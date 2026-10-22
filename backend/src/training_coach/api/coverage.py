"""The body map on the Plan tab (``GET /api/plan/coverage``, program-builder.md F). Owner-only.

Apart from ``GET /api/plan``, which serves only the bundled plan: this one counts the spine
warning at the person's own ladder steps.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain import coverage as domain
from training_coach.domain.coverage import Band, Evidence
from training_coach.services import coverage as service

router = APIRouter(prefix="/api/plan", tags=["plan"])


class SourceView(BaseModel):
    session: str
    exercise: str
    sets: int
    weight: float  # what one set counts for this muscle (ADR-0064)


class MuscleView(BaseModel):
    muscle: str
    main: bool  # one of the ten main muscles
    sets: float  # fractional hard sets a week
    days: int  # sessions with at least 2 sets for it
    most: float  # the most in one session
    most_in: str | None
    band: Band
    low: float  # its green band
    high: float
    evidence: Evidence | None  # None: the general band
    one_day: bool  # trained, but not on the two days green needs
    over_session_cap: bool
    back_to_back: list[str]  # two sessions running that both load it hard; empty if none
    missing_parts: list[str]  # parts no exercise reaches: triceps long head, rectus femoris
    sources: list[SourceView]


class SessionLoadView(BaseModel):
    session: str
    spine_sets: int
    grip_sets: int
    spine_heavy: bool
    grip_heavy: bool


class CoverageView(BaseModel):
    muscles: list[MuscleView]  # main muscles first
    sessions: list[SessionLoadView]  # queue order
    main_on_target: int  # main muscles in the green band
    main_total: int
    session_cap: int
    back_to_back: int
    spine_cap: int
    grip_cap: int
    minimum: int
    ceiling: int


@router.get("/coverage", response_model=CoverageView)
def get_coverage(request: Request, user: Owner) -> CoverageView:
    """Weekly fractional sets per muscle with its band and warnings, from the plan as it
    stands; nothing here changes it."""
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        found = service.plan_coverage(session)
    return CoverageView(
        muscles=[
            MuscleView(
                muscle=m.muscle,
                main=m.main,
                sets=m.sets,
                days=m.days,
                most=m.most,
                most_in=m.most_in,
                band=m.band,
                low=m.target.low,
                high=m.target.high,
                evidence=m.target.evidence,
                one_day=m.one_day,
                over_session_cap=m.over_session_cap,
                back_to_back=list(m.back_to_back or ()),
                missing_parts=list(m.missing_parts),
                sources=[SourceView(**vars(s)) for s in m.sources],
            )
            for m in found.muscles
        ],
        sessions=[
            SessionLoadView(
                session=d.name,
                spine_sets=d.spine_sets,
                grip_sets=d.grip_sets,
                spine_heavy=d.spine_heavy,
                grip_heavy=d.grip_heavy,
            )
            for d in found.days
        ],
        main_on_target=found.main_on_target,
        main_total=len(domain.MAIN),
        session_cap=domain.SESSION_CAP,
        back_to_back=domain.BACK_TO_BACK,
        spine_cap=domain.SPINE_CAP,
        grip_cap=domain.GRIP_CAP,
        minimum=domain.MINIMUM,
        ceiling=domain.CEILING,
    )
