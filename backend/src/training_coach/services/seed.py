"""Load the training plan from ``seed/plan.toml`` into the database (phase 1, step 1-B).

The seed is idempotent: running it again changes nothing. It is also safe to run after the
plan file has been edited:

- exercises, ladder steps and sessions are matched by slug / position and updated in place;
  a ladder step that history uses keeps its name unless the exercise lists a rename;
- new ones are added; nothing is deleted (removing things is a deliberate migration);
- progress is never reset: existing exercise state, queue pointer and settings are kept.
"""

import tomllib
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Literal, Self

import structlog
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    LadderStep,
    PlanState,
    SessionTemplate,
    SetLog,
    TemplateItem,
    UserSettings,
)
from training_coach.domain.enums import ExerciseKind

log = structlog.get_logger(__name__)

SLUG = r"^[a-z0-9]+(-[a-z0-9]+)*$"
_PARK_OFFSET = 10_000


class SeedError(RuntimeError):
    """The plan file cannot be applied to the current database."""


# ------------------------------------------------------------------ file schema


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ExerciseSeed(_Strict):
    slug: str = Field(pattern=SLUG, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    kind: ExerciseKind
    muscle_groups: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    start: int = Field(ge=0)
    ladder: list[str] = Field(min_length=1)
    # old name -> new name: renames a step in place, keeping its history (see _preflight)
    renames: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _start_within_ladder(self) -> Self:
        if self.start >= len(self.ladder):
            raise ValueError(f"{self.slug}: start {self.start} is beyond the ladder")
        missing = sorted(set(self.renames.values()) - set(self.ladder))
        if missing:
            raise ValueError(f"{self.slug}: renames to {missing}, which is not in its ladder")
        return self


class ItemSeed(_Strict):
    exercise: str
    sets: int = Field(ge=1, le=20)
    rep_min: int = Field(ge=1)
    rep_max: int = Field(ge=1)
    per_side: bool = False

    @model_validator(mode="after")
    def _range(self) -> Self:
        if self.rep_max < self.rep_min:
            raise ValueError(f"{self.exercise}: rep_max < rep_min")
        return self


class SessionSeed(_Strict):
    slug: str = Field(pattern=SLUG, max_length=64)
    type: Literal["strength", "conditioning", "recovery"] = "strength"
    name: str = Field(min_length=1, max_length=120)
    focus: str = Field(min_length=1, max_length=120)
    is_rest_optional: bool = False
    items: list[ItemSeed] = Field(min_length=1)


class PlanSeed(_Strict):
    exercises: list[ExerciseSeed] = Field(min_length=1)
    sessions: list[SessionSeed] = Field(min_length=1)

    @model_validator(mode="after")
    def _references(self) -> Self:
        slugs = [e.slug for e in self.exercises]
        if len(slugs) != len(set(slugs)):
            raise ValueError("duplicate exercise slug")
        session_slugs = [s.slug for s in self.sessions]
        if len(session_slugs) != len(set(session_slugs)):
            raise ValueError("duplicate session slug")
        known = set(slugs)
        for session in self.sessions:
            for item in session.items:
                if item.exercise not in known:
                    raise ValueError(f"session {session.slug}: unknown exercise {item.exercise}")
        return self


def load_plan(text: str | None = None) -> PlanSeed:
    """Parse and validate the plan. Defaults to the bundled ``seed/plan.toml``."""
    if text is None:
        return bundled_plan()
    return PlanSeed.model_validate(tomllib.loads(text))


@lru_cache(maxsize=1)
def bundled_plan() -> PlanSeed:
    """The bundled plan, parsed once per process (the file ships inside the image)."""
    text = files("training_coach.seed").joinpath("plan.toml").read_text(encoding="utf-8")
    return PlanSeed.model_validate(tomllib.loads(text))


# ----------------------------------------------------------------------- apply


@dataclass
class SeedResult:
    created: int = 0
    updated: int = 0
    deleted: int = 0

    @property
    def changed(self) -> bool:
        return self.created > 0 or self.updated > 0 or self.deleted > 0


def _preflight(session: Session, plan: PlanSeed, exercises: dict[str, Exercise]) -> None:
    """Refuse plans that would drop things history depends on, before any write."""
    existing_sessions = set(session.scalars(select(SessionTemplate.slug)))
    removed = sorted(existing_sessions - {s.slug for s in plan.sessions})
    if removed:
        # Sessions define the queue (ADR-0006); dropping one would orphan it in the cycle.
        raise SeedError(
            f"sessions {removed} exist in the database but not in plan.toml; "
            "removing a session needs a data migration (see docs/specs/phase-1-daily-loop.md)"
        )
    in_use = set(session.scalars(select(SetLog.ladder_step_id).distinct())) | set(
        session.scalars(select(ExerciseState.ladder_step_id))
    )
    for seed in plan.exercises:
        exercise = exercises.get(seed.slug)
        if exercise is None:
            continue
        if len(exercise.ladder) > len(seed.ladder):
            raise SeedError(
                f"exercise {seed.slug!r} has {len(exercise.ladder)} ladder steps in the database "
                f"but {len(seed.ladder)} in plan.toml; logged sets reference ladder steps, so "
                "shortening a ladder needs a data migration"
            )
        # Steps are matched by position, so a new name at a used position would silently move
        # logged sets and current progress to a different variation (#18).
        for step in exercise.ladder:
            new = seed.ladder[step.position]
            if new != step.name and step.id in in_use and seed.renames.get(step.name) != new:
                raise SeedError(
                    f"exercise {seed.slug!r} step {step.position + 1} is {step.name!r} in the "
                    f"database but {new!r} in plan.toml, and logged sets or current progress "
                    "use it. Add new steps at the end of the ladder; to fix the name of the "
                    f'same step, add renames = {{ "{step.name}" = "{new}" }} to the exercise'
                )


def _set(obj: object, result: SeedResult, **values: object) -> None:
    """Assign attributes, counting an update only when something actually changes."""
    dirty = False
    for key, value in values.items():
        if getattr(obj, key) != value:
            setattr(obj, key, value)
            dirty = True
    if dirty:
        result.updated += 1


def apply_seed(session: Session, plan: PlanSeed) -> SeedResult:
    """Upsert the plan. The caller owns the transaction (commit / rollback).

    Raises ``SeedError`` before changing anything if the plan would remove a session, shorten
    a ladder, or rename a ladder step that history uses without a ``renames`` entry: all would
    remap or orphan logged history.
    Items removed from a session are deleted (nothing else references them).
    """
    result = SeedResult()

    exercises = {e.slug: e for e in session.scalars(select(Exercise))}
    _preflight(session, plan, exercises)
    for seed in plan.exercises:
        exercise = exercises.get(seed.slug)
        if exercise is None:
            exercise = Exercise(slug=seed.slug)
            session.add(exercise)
            exercises[seed.slug] = exercise
            result.created += 1
            exercise.name, exercise.kind = seed.name, seed.kind.value
            exercise.muscle_groups, exercise.aliases = list(seed.muscle_groups), list(seed.aliases)
        else:
            _set(
                exercise,
                result,
                name=seed.name,
                kind=seed.kind.value,
                muscle_groups=list(seed.muscle_groups),
                aliases=list(seed.aliases),
            )
        steps = {step.position: step for step in exercise.ladder}
        for position, name in enumerate(seed.ladder):
            step = steps.get(position)
            if step is None:
                exercise.ladder.append(LadderStep(position=position, name=name))
                result.created += 1
            else:
                _set(step, result, name=name)
    session.flush()

    for seed in plan.exercises:
        exercise = exercises[seed.slug]
        if session.get(ExerciseState, exercise.id) is None:
            start_step = next(s for s in exercise.ladder if s.position == seed.start)
            session.add(ExerciseState(exercise_id=exercise.id, ladder_step_id=start_step.id))
            result.created += 1

    templates = {t.slug: t for t in session.scalars(select(SessionTemplate))}
    wanted = {s.slug: i for i, s in enumerate(plan.sessions)}
    current = {t.slug: t.position for t in templates.values()}
    if current != {slug: wanted[slug] for slug in current}:
        # Reordering: park existing positions out of the way so the unique index never
        # sees two sessions on one position mid-update. New sessions always get positions
        # after the existing ones' final positions, so they cannot collide.
        for existing in templates.values():
            existing.position += _PARK_OFFSET
        session.flush()
    for position, seed_session in enumerate(plan.sessions):
        template = templates.get(seed_session.slug)
        if template is None:
            template = SessionTemplate(slug=seed_session.slug, position=position)
            session.add(template)
            templates[seed_session.slug] = template
            result.created += 1
            template.name, template.focus = seed_session.name, seed_session.focus
            template.is_rest_optional = seed_session.is_rest_optional
        else:
            _set(
                template,
                result,
                position=position,
                name=seed_session.name,
                focus=seed_session.focus,
                is_rest_optional=seed_session.is_rest_optional,
            )
        items = {item.position: item for item in template.items}
        for item_position, item_seed in enumerate(seed_session.items):
            values = {
                "exercise_id": exercises[item_seed.exercise].id,
                "sets": item_seed.sets,
                "rep_min": item_seed.rep_min,
                "rep_max": item_seed.rep_max,
                "per_side": item_seed.per_side,
            }
            item = items.get(item_position)
            if item is None:
                template.items.append(TemplateItem(position=item_position, **values))
                result.created += 1
            else:
                _set(item, result, **values)
        for position, item in items.items():
            if position >= len(seed_session.items):
                template.items.remove(item)  # delete-orphan: removed from the plan
                result.deleted += 1
    session.flush()

    if session.get(PlanState, 1) is None:
        first = templates[plan.sessions[0].slug]
        session.add(PlanState(id=1, next_template_id=first.id))
        result.created += 1
    if session.get(UserSettings, 1) is None:
        session.add(UserSettings(id=1))
        result.created += 1

    counts = {"created": result.created, "updated": result.updated, "deleted": result.deleted}
    if result.changed:
        session.add(Event(kind="seed.applied", payload=counts))
        log.info("seed.applied", **counts)
    else:
        log.info("seed.unchanged")
    return result
