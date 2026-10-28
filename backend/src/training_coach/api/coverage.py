"""The body map on the Plan tab (``GET /api/plan/coverage``, program-builder.md F). Owner-only.

Apart from ``GET /api/plan``, which serves only the bundled plan: this one counts the spine
warning at the person's own ladder steps, and the home or gym versions (``place``, ADR-0071).
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain import coverage as domain
from training_coach.domain.coverage import Band, Evidence, Heat
from training_coach.domain.enums import Place, Places
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


class SessionMuscleView(BaseModel):
    muscle: str
    sets: float  # fractional hard sets in this session
    heat: Heat  # how hard the session works it (ADR-0069)


class SessionLoadView(BaseModel):
    session: str
    slug: str  # the session template's, as in GET /api/plan
    place: Place  # the version counted: home in the gym view when it has no gym version
    spine_sets: int
    grip_sets: int
    spine_heavy: bool
    grip_heavy: bool
    muscles: list[SessionMuscleView]  # only those it works, main muscles first


class CoverageView(BaseModel):
    place: Place  # the versions counted
    places: Places  # where the person trains: Home | Gym is offered at both
    muscles: list[MuscleView]  # main muscles first
    sessions: list[SessionLoadView]  # queue order
    main_on_target: int  # main muscles in the green band
    main_total: int
    session_cap: int
    back_to_back: int
    spine_cap: int
    grip_cap: int
    hard_from: int  # one session's sets from which a muscle is worked hard
    minimum: int
    ceiling: int


@router.get("/coverage", response_model=CoverageView)
def get_coverage(request: Request, user: Owner, place: Place | None = None) -> CoverageView:
    """Weekly fractional sets per muscle with its band and warnings, from the plan as it
    stands, counting each session's version at ``place`` (default: the day's place); nothing
    here changes it, not even the place Today starts at."""
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        places, day = service.map_place(session)
        at = day if place is None else place
        found = service.plan_coverage(session, at)
    return CoverageView(
        place=at,
        places=places,
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
                slug=d.slug,
                place=d.place,
                spine_sets=d.spine_sets,
                grip_sets=d.grip_sets,
                spine_heavy=d.spine_heavy,
                grip_heavy=d.grip_heavy,
                muscles=[
                    SessionMuscleView(muscle=m, sets=n, heat=domain.heat(n)) for m, n in d.muscles
                ],
            )
            for d in found.days
        ],
        main_on_target=found.main_on_target,
        main_total=len(domain.MAIN),
        session_cap=domain.SESSION_CAP,
        back_to_back=domain.BACK_TO_BACK,
        spine_cap=domain.SPINE_CAP,
        grip_cap=domain.GRIP_CAP,
        hard_from=domain.HARD_FROM,
        minimum=domain.MINIMUM,
        ceiling=domain.CEILING,
    )
