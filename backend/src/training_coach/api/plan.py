"""Read-only view of the person's training plan for the dashboard (``GET /api/plan``), each
session with its home version and its gym one (ADR-0071), from their rows (ADR-0073). What an
exercise is comes from the catalogue. Progress stays out: it has its own routes.
"""

from collections.abc import Iterable
from datetime import UTC, date, datetime
from typing import Literal, cast

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import ExerciseKind, Place
from training_coach.domain.queue import local_date
from training_coach.domain.volume import TARGET_MAX_SETS, TARGET_MIN_SETS, weekly_sets
from training_coach.services import plan_edit, plan_import
from training_coach.services.plan_rows import PlannedItem, PlannedSession, planned_sessions
from training_coach.services.seed import ExerciseSeed, bundled_plan
from training_coach.services.users import OWNER

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


class EditItemView(BaseModel):
    exercise: str  # slug
    name: str
    sets: int
    rep_min: int
    rep_max: int
    per_side: bool
    pair: int | None


class EditSessionView(BaseModel):
    slug: str
    name: str
    focus: str
    home: list[EditItemView]
    gym: list[EditItemView]  # empty: done the same way at the gym
    away: list[EditItemView]  # empty: no away version


class CatalogueItemView(BaseModel):
    slug: str
    name: str
    kind: ExerciseKind
    per_side: bool
    muscles: dict[str, float]
    pattern: str
    places: list[Place]  # where it can be planned
    range: tuple[int, int] | None  # the catalogue's reps for it, when it has its own
    first_step: str  # its easiest step, which its picture shows
    levels: tuple[int, int] | None  # who it is for, from its first step to its last (ADR-0083)
    needs: list[str]  # what its first step needs, in words; empty: no kit
    lengthened: bool  # a lengthened-position pick (program-builder.md, Decided 5)


class PlanEditView(BaseModel):
    revision: str
    sessions: list[EditSessionView]
    catalogue: list[CatalogueItemView]


def _edit_items(rows: Iterable[plan_edit.ItemEdit], names: dict[str, str]) -> list[EditItemView]:
    return [
        EditItemView(
            exercise=i.exercise,
            name=names.get(i.exercise, i.exercise),
            sets=i.sets,
            rep_min=i.rep_min,
            rep_max=i.rep_max,
            per_side=i.per_side,
            pair=i.pair,
        )
        for i in rows
    ]


@router.get("/plan/edit", response_model=PlanEditView)
def get_plan_edit(request: Request, user: Owner) -> PlanEditView:
    """The person's sessions with every version, and what they can choose from."""
    exercises = [e for e in bundled_plan().exercises if not e.retired]
    names = {e.slug: e.name for e in exercises}
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        sessions = [
            EditSessionView(
                slug=t.slug,
                name=t.name,
                focus=t.focus,
                home=_edit_items(t.home, names),
                gym=_edit_items(t.gym, names),
                away=_edit_items(t.away, names),
            )
            for t in plan_edit.editable(session)
        ]
        revision = plan_edit.revision(session)
    return PlanEditView(
        revision=revision,
        sessions=sessions,
        catalogue=[
            CatalogueItemView(
                slug=e.slug,
                name=e.name,
                kind=e.kind,
                per_side=e.per_side,
                muscles=dict(e.muscles),
                pattern=e.pattern,
                places=plan_edit.places_for(e),
                range=e.range,
                first_step=e.ladder[0],
                levels=plan_edit.level_range(e),
                needs=plan_edit.first_needs(e),
                lengthened=e.lengthened,
            )
            for e in exercises
        ],
    )


class ItemChange(BaseModel):
    exercise: str = Field(max_length=64)
    sets: int = Field(ge=1, le=20)
    rep_min: int = Field(ge=1, le=600)
    rep_max: int = Field(ge=1, le=600)
    per_side: bool = False
    pair: int | None = Field(default=None, ge=1)


class VersionChange(BaseModel):
    slug: str = Field(max_length=64)
    place: Place
    items: list[ItemChange] = Field(max_length=40)


class PlanChanges(BaseModel):
    revision: str = Field(max_length=32)
    note: str = Field(min_length=1, max_length=120)  # a short "what changed" (ADR-0073)
    versions: list[VersionChange] = Field(min_length=1, max_length=30)


class PlanSavedView(BaseModel):
    revision: str
    version: str | None  # the note it was saved under; None: nothing differed


@router.post("/plan/changes", response_model=PlanSavedView)
def post_plan_changes(request: Request, user: Owner, body: PlanChanges) -> PlanSavedView:
    """Save a draft of the person's own plan as one version. A draft of an older plan, or a
    session in progress, is a conflict; what the app couldn't run is refused with the reason."""
    edits = [
        plan_edit.VersionEdit(
            slug=v.slug,
            place=v.place,
            items=tuple(plan_edit.ItemEdit(**i.model_dump()) for i in v.items),
        )
        for v in body.versions
    ]
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        saved = plan_edit.save(
            session, edits, body.note.strip(), body.revision, bundled_plan(), _today(request)
        )
    if saved in (plan_edit.STALE, plan_edit.IN_PROGRESS):
        raise HTTPException(status.HTTP_409_CONFLICT, saved)
    if isinstance(saved, str):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, saved)
    return PlanSavedView(revision=saved.revision, version=saved.version)


class PlanImportView(BaseModel):
    changes: list[str]  # what saving would change, in words; empty: nothing waits
    blocked: str | None  # why it can't be saved now
    version: str | None  # what the new version would be called


def _today(request: Request) -> date:
    return local_date(datetime.now(UTC), request.app.state.settings.tz)


@router.get("/plan/import", response_model=PlanImportView)
def get_plan_import(request: Request, user: Owner) -> PlanImportView:
    """What ``plan.toml`` would change in the owner's plan (ADR-0073); nothing for anyone else."""
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        found = plan_import.preview(session, bundled_plan(), _today(request))
    return PlanImportView(changes=list(found.changes), blocked=found.blocked, version=found.version)


@router.post("/plan/import", response_model=PlanImportView)
def post_plan_import(request: Request, user: Owner) -> PlanImportView:
    """Save it as one version: the owner's alone, anyone else is refused (Liam, 5 Nov 2026).
    Answers what was saved; a change that can't be saved now is a conflict."""
    if user != OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "the plan import is the owner's")
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        found = plan_import.save(session, bundled_plan(), _today(request))
    if found.blocked:
        raise HTTPException(status.HTTP_409_CONFLICT, found.blocked)
    return PlanImportView(changes=list(found.changes), blocked=None, version=found.version)
