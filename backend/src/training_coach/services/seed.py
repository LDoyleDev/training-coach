"""Load the training plan from ``seed/plan.toml`` into the database (phase 1, step 1-B).

The seed is idempotent: running it again changes nothing. It is also safe to run after the
plan file has been edited:

- exercises, ladder steps and sessions are matched by slug / position and updated in place;
  a ladder step that history uses keeps its name unless the exercise lists a rename;
- new ones are added; nothing is deleted (removing things is a deliberate migration);
- progress is never reset: existing exercise state, queue pointer and settings are kept;
- plan versions are matched by date; one that workouts record can't be removed or re-dated,
  and every workout gets the one in force on its date (ADR-0034).
"""

import tomllib
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from importlib.resources import files
from typing import Annotated, Literal, Self

import structlog
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    FitnessTestDay,
    LadderStep,
    PlanState,
    PlanVersion,
    SessionTemplate,
    SetLog,
    TemplateItem,
    User,
    UserSettings,
    Workout,
    version_on,
)
from training_coach.db.session import ALL_USERS
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.fitness_tests import DAYS, FitnessTest, Unit
from training_coach.domain.load import LoadKit
from training_coach.domain.mobility_flow import Flow, Move
from training_coach.domain.muscles import (
    PART_OF,
    WEIGHTS,
    Muscle,
    Part,
    Pattern,
    Quality,
    Stress,
    parse_need,
    step_stress,
)
from training_coach.domain.parser import normalise_name
from training_coach.domain.stretching import Stretch

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
    # How to do it, in a sentence or two (#116): the guided session and the bot show it.
    # Read from the bundled plan, like the stretches: nothing logged refers to it.
    summary: str | None = Field(default=None, max_length=300)
    # The catalogue's facts (ADR-0064), read from the bundled plan like the summary: muscles
    # with their weights, qualities that aren't muscles, the muscle parts it reaches, its
    # movement pattern, the shared stress it adds, and the kit each ladder step needs.
    muscles: dict[Muscle, float] = Field(default_factory=dict)
    qualities: list[Quality] = Field(default_factory=list)
    parts: list[Part] = Field(default_factory=list)
    pattern: Pattern
    stress: list[Stress] = Field(default_factory=list)
    needs: dict[str, list[str]] = Field(default_factory=dict)  # ladder step -> kit
    # ladder step -> how to do it (kit-ladder-proposal.md); written on every run, not history
    cues: dict[str, Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=dict
    )
    # ladder step -> what carries its weight: the step takes load (ADR-0072); read from the
    # bundled plan like needs
    loads: dict[str, LoadKit] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)
    start: int = Field(ge=0)
    ladder: list[str] = Field(min_length=1)
    # old name -> new name: renames a step in place, keeping its history (see _preflight)
    renames: dict[str, str] = Field(default_factory=dict)
    # No longer in the plan, but its history stays and old days can still be logged
    # (#107, ADR-0034). Retired exercises are never deleted and can't be in a session.
    retired: bool = False
    # One side at a time, for logs of an exercise no session uses (a retired one).
    per_side: bool = False

    @model_validator(mode="after")
    def _start_within_ladder(self) -> Self:
        if self.start >= len(self.ladder):
            raise ValueError(f"{self.slug}: start {self.start} is beyond the ladder")
        repeated = sorted({name for name in self.ladder if self.ladder.count(name) > 1})
        if repeated:
            raise ValueError(f"{self.slug}: ladder step {repeated} appears twice")
        missing = sorted(set(self.renames.values()) - set(self.ladder))
        if missing:
            raise ValueError(f"{self.slug}: renames to {missing}, which is not in its ladder")
        return self

    def step_stress(self, step: str) -> set[Stress]:
        """The shared stress of one of its ladder steps (a squat loads the spine only loaded:
        with a weight it needs, or on a step that takes load, ADR-0072)."""
        if step in self.loads:
            return set(self.stress)
        return step_stress(self.stress, self.pattern, self.needs.get(step, []))

    @model_validator(mode="after")
    def _catalogue(self) -> Self:
        if not self.muscles and not self.qualities:
            raise ValueError(f"{self.slug}: say which muscles or qualities it trains")
        odd = sorted(m for m, w in self.muscles.items() if w not in WEIGHTS)
        if odd:  # a stabiliser is left out: it counts 0
            raise ValueError(f"{self.slug}: weights for {odd} must be 1, 0.5 or 0.25")
        for part in self.parts:
            if PART_OF[part] not in self.muscles:
                raise ValueError(f"{self.slug}: reaches the {part} but doesn't train its muscle")
        unknown = sorted(set(self.needs) - set(self.ladder))
        if unknown:
            raise ValueError(f"{self.slug}: needs for {unknown}, which is not in its ladder")
        unknown = sorted(set(self.cues) - set(self.ladder))
        if unknown:
            raise ValueError(f"{self.slug}: cues for {unknown}, which is not in its ladder")
        unknown = sorted(set(self.loads) - set(self.ladder))
        if unknown:
            raise ValueError(f"{self.slug}: loads for {unknown}, which is not in its ladder")
        if self.loads and self.kind is not ExerciseKind.REPS:
            raise ValueError(f"{self.slug}: only an exercise counted in reps takes load")
        for step, kit in self.needs.items():
            try:
                for need in kit:
                    parse_need(need)
            except ValueError as error:
                raise ValueError(f"{self.slug}, {step!r}: {error}") from None
        return self


class ItemSeed(_Strict):
    exercise: str
    sets: int = Field(ge=1, le=20)
    rep_min: int = Field(ge=1)
    rep_max: int = Field(ge=1)
    per_side: bool = False
    # Two neighbouring items with the same number are done alternately (#97).
    pair: int | None = Field(default=None, ge=1)

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
    # The gym version (ADR-0071); empty: done the same way at the gym.
    gym: list[ItemSeed] = Field(default_factory=list)

    @model_validator(mode="after")
    def _pairs(self) -> Self:
        """Each pair number marks exactly two items, next to each other, in each version."""
        for version in (self.items, self.gym):
            numbers = [item.pair for item in version]
            for number in {n for n in numbers if n is not None}:
                where = [i for i, n in enumerate(numbers) if n == number]
                if len(where) != 2 or where[1] != where[0] + 1:
                    raise ValueError(
                        f"session {self.slug}: pair {number} must be two neighbouring items"
                    )
        return self


class StretchSeed(_Strict):
    """A stretch offered after a resistance session (#98). Read from the bundled plan, not
    stored: nothing logged refers to a stretch."""

    slug: str = Field(pattern=SLUG, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    muscles: list[Muscle] = Field(min_length=1)
    per_side: bool = False
    cue: str = Field(min_length=1, max_length=200)

    def stretch(self) -> Stretch:
        return Stretch(self.slug, self.name, frozenset(self.muscles), self.per_side, self.cue)


class FlowMoveSeed(_Strict):
    """One movement of the mobility flow (ADR-0062). ``seconds`` is per side when one-sided."""

    slug: str = Field(pattern=SLUG, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    seconds: int = Field(ge=15, le=300)
    per_side: bool = False
    target: str = Field(min_length=1, max_length=80)
    start: str = Field(min_length=1, max_length=200)
    end: str = Field(min_length=1, max_length=200)
    cues: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(
        min_length=1, max_length=2
    )
    breathing: str = Field(min_length=1, max_length=120)
    easier: str = Field(min_length=1, max_length=200)
    pacing: str = Field(min_length=1, max_length=120)

    def move(self) -> Move:
        return Move(
            self.slug,
            self.name,
            self.seconds,
            self.per_side,
            self.target,
            self.start,
            self.end,
            tuple(self.cues),
            self.breathing,
            self.easier,
            self.pacing,
        )


class MobilitySeed(_Strict):
    """The guided mobility flow and the exercise it is logged as (ADR-0062)."""

    exercise: str = Field(pattern=SLUG, max_length=64)
    safety: str = Field(min_length=1, max_length=200)
    moves: list[FlowMoveSeed] = Field(min_length=1)

    @model_validator(mode="after")
    def _whole(self) -> Self:
        slugs = [m.slug for m in self.moves]
        if len(slugs) != len(set(slugs)):
            raise ValueError("duplicate flow movement slug")
        total = self.flow().seconds
        if total % 60:  # it is logged in whole minutes
            raise ValueError(f"the mobility flow must last whole minutes, not {total} s")
        return self

    def flow(self) -> Flow:
        return Flow(self.exercise, self.safety, tuple(m.move() for m in self.moves))


class TestSeed(_Strict):
    """A baseline test (2-A, #94). Read from the bundled plan; results name it by slug."""

    slug: str = Field(pattern=SLUG, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    day: int
    unit: Unit
    per_side: bool = False
    cue: str = Field(min_length=1, max_length=300)

    def test(self) -> FitnessTest:
        return FitnessTest(self.slug, self.name, self.day, self.unit, self.per_side, self.cue)


class VersionSeed(_Strict):
    """A version of the plan and the day it took over (#107, ADR-0034)."""

    since: date
    name: str = Field(min_length=1, max_length=120)


class PlanSeed(_Strict):
    exercises: list[ExerciseSeed] = Field(min_length=1)
    sessions: list[SessionSeed] = Field(min_length=1)
    stretches: list[StretchSeed] = Field(default_factory=list)
    versions: list[VersionSeed] = Field(default_factory=list)  # oldest first
    tests: list[TestSeed] = Field(default_factory=list)
    mobility: MobilitySeed | None = None

    @model_validator(mode="after")
    def _references(self) -> Self:
        tests = [t.slug for t in self.tests]
        if len(tests) != len(set(tests)):
            raise ValueError("duplicate test slug")
        for test in self.tests:
            if test.day not in DAYS:
                raise ValueError(f"test {test.slug}: day must be one of {DAYS}")
        days = [v.since for v in self.versions]
        if days != sorted(set(days)):
            raise ValueError("plan versions must be in date order, one per day")
        slugs = [e.slug for e in self.exercises]
        if len(slugs) != len(set(slugs)):
            raise ValueError("duplicate exercise slug")
        session_slugs = [s.slug for s in self.sessions]
        if len(session_slugs) != len(set(session_slugs)):
            raise ValueError("duplicate session slug")
        owners: dict[str, str] = {}
        for exercise in self.exercises:
            for name in {normalise_name(n) for n in (exercise.name, *exercise.aliases)}:
                other = owners.setdefault(name, exercise.slug)
                if other != exercise.slug:
                    raise ValueError(
                        f"the name {name!r} is used by both {other} and {exercise.slug}"
                    )
        stretch_slugs = [s.slug for s in self.stretches]
        if len(stretch_slugs) != len(set(stretch_slugs)):
            raise ValueError("duplicate stretch slug")
        worked = {m for e in self.exercises for m in e.muscles}
        for stretch in self.stretches:
            unknown = sorted(set(stretch.muscles) - worked)
            if unknown:  # it would never match a session's muscles
                raise ValueError(f"stretch {stretch.slug}: no exercise works {unknown}")
        known = set(slugs)
        if self.mobility is not None:
            logged = next((e for e in self.exercises if e.slug == self.mobility.exercise), None)
            if logged is None or logged.kind is not ExerciseKind.DURATION_MIN:
                raise ValueError(
                    f"the mobility flow is logged as {self.mobility.exercise}, "
                    "which must be an exercise counted in minutes"
                )
        retired = {e.slug for e in self.exercises if e.retired}
        for session in self.sessions:
            for item in (*session.items, *session.gym):
                if item.exercise not in known:
                    raise ValueError(f"session {session.slug}: unknown exercise {item.exercise}")
                if item.exercise in retired:
                    raise ValueError(
                        f"session {session.slug} uses {item.exercise}, which is retired; "
                        "un-retire it or take it out of the session"
                    )
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
    # Every person's history protects the shared ladders, whoever this session is bound to.
    everyone = {ALL_USERS: True}
    in_use = set(
        session.scalars(select(SetLog.ladder_step_id).distinct(), execution_options=everyone)
    ) | set(session.scalars(select(ExerciseState.ladder_step_id), execution_options=everyone))
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
        by_name = {step.name: step for step in exercise.ladder}
        for step in exercise.ladder:
            new = seed.ladder[step.position]
            if new == step.name:
                continue
            other = by_name.get(new)
            if other is not None:
                # A swap, a chain of renames or an insert dressed up as renames: a rename can't
                # make any of these safe, so don't offer one.
                raise SeedError(
                    f"exercise {seed.slug!r} step {step.position + 1} would become {new!r}, "
                    f"which is already the name of step {other.position + 1}. Moving a name "
                    "between steps moves its logged sets and progress; add new steps at the end "
                    "of the ladder instead"
                )
            if step.id in in_use and seed.renames.get(step.name) != new:
                raise SeedError(
                    f"exercise {seed.slug!r} step {step.position + 1} is {step.name!r} in the "
                    f"database but {new!r} in plan.toml, and logged sets or current progress "
                    "use it. Add new steps at the end of the ladder; to fix the name of the "
                    f'same step, add renames = {{ "{step.name}" = "{new}" }} to the exercise'
                )


def _versions_preflight(session: Session, plan: PlanSeed) -> None:
    """A version workouts record stays: removing or re-dating it would rewrite their history."""
    kept = {v.since for v in plan.versions}
    recorded = session.execute(
        select(PlanVersion.since, PlanVersion.name)
        .join(Workout, Workout.plan_version_id == PlanVersion.id)
        .distinct(),
        execution_options={ALL_USERS: True},
    )
    for since, name in recorded:
        if since not in kept:
            raise SeedError(
                f"plan version {name!r} (since {since}) is recorded on workouts but not in "
                "plan.toml; keep it there (its name can change, its date can't)"
            )


def _tests_preflight(session: Session, plan: PlanSeed) -> None:
    """A test with results stays in the plan: its results name it."""
    kept = {t.slug for t in plan.tests}
    days = session.scalars(select(FitnessTestDay), execution_options={ALL_USERS: True})
    recorded = {r["test"] for day in days for r in day.results}
    missing = sorted(recorded - kept)
    if missing:
        raise SeedError(f"tests {missing} have results but are not in plan.toml; keep them there")


def _apply_versions(session: Session, plan: PlanSeed, result: SeedResult) -> None:
    existing = {v.since: v for v in session.scalars(select(PlanVersion))}
    for seed in plan.versions:
        version = existing.pop(seed.since, None)
        if version is None:
            session.add(PlanVersion(since=seed.since, name=seed.name))
            result.created += 1
        else:
            _set(version, result, name=seed.name)
    for version in existing.values():  # unrecorded (the preflight checked)
        session.delete(version)
        result.deleted += 1
    session.flush()
    # Every workout carries the version in force on its date: one saved before its version
    # existed, or one a version added between two others now covers, is brought up to date.
    on_date = version_on(Workout.local_date)
    filled = session.execute(
        update(Workout)
        .where(Workout.plan_version_id.is_distinct_from(on_date))
        .values(plan_version_id=on_date),
        execution_options={ALL_USERS: True},
    )
    result.updated += getattr(filled, "rowcount", 0)  # an UPDATE gives a CursorResult


def _set(obj: object, result: SeedResult, **values: object) -> None:
    """Assign attributes, counting an update only when something actually changes."""
    dirty = False
    for key, value in values.items():
        if getattr(obj, key) != value:
            setattr(obj, key, value)
            dirty = True
    if dirty:
        result.updated += 1


def _version(
    items: list[TemplateItem],
    seeds: list[ItemSeed],
    exercises: dict[str, Exercise],
    result: SeedResult,
) -> None:
    """Make one version of a session (its home or gym items, ADR-0071) match the plan: items
    matched by position, added at the end, and removed past the plan's last."""
    found = {item.position: item for item in items}
    for position, seed in enumerate(seeds):
        values = {
            "exercise_id": exercises[seed.exercise].id,
            "sets": seed.sets,
            "rep_min": seed.rep_min,
            "rep_max": seed.rep_max,
            "per_side": seed.per_side,
            "pair": seed.pair,
        }
        item = found.get(position)
        if item is None:
            items.append(TemplateItem(position=position, **values))
            result.created += 1
        else:
            _set(item, result, **values)
    for position, item in found.items():
        if position >= len(seeds):
            items.remove(item)  # delete-orphan: removed from the plan
            result.deleted += 1


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
    _versions_preflight(session, plan)
    _tests_preflight(session, plan)
    for seed in plan.exercises:
        exercise = exercises.get(seed.slug)
        if exercise is None:
            exercise = Exercise(slug=seed.slug)
            session.add(exercise)
            exercises[seed.slug] = exercise
            result.created += 1
            exercise.name, exercise.kind = seed.name, seed.kind.value
            exercise.aliases = list(seed.aliases)
            exercise.retired, exercise.per_side = seed.retired, seed.per_side
        else:
            _set(
                exercise,
                result,
                name=seed.name,
                kind=seed.kind.value,
                aliases=list(seed.aliases),
                retired=seed.retired,
                per_side=seed.per_side,
            )
        steps = {step.position: step for step in exercise.ladder}
        for position, name in enumerate(seed.ladder):
            step = steps.get(position)
            cue = seed.cues.get(name)
            if step is None:
                exercise.ladder.append(LadderStep(position=position, name=name, cue=cue))
                result.created += 1
            else:
                _set(step, result, name=name, cue=cue)
    session.flush()

    # Each person's own rows: where they are on every ladder (ADR-0026). The seed runs in an
    # unbound session, so every per-person query here names the user.
    people = list(session.scalars(select(User.id).order_by(User.id)))
    for user_id in people:
        started = set(
            session.scalars(
                select(ExerciseState.exercise_id).where(ExerciseState.user_id == user_id),
                execution_options={ALL_USERS: True},
            )
        )
        for seed in plan.exercises:
            exercise = exercises[seed.slug]
            if exercise.id not in started:
                start_step = next(s for s in exercise.ladder if s.position == seed.start)
                session.add(
                    ExerciseState(
                        user_id=user_id, exercise_id=exercise.id, ladder_step_id=start_step.id
                    )
                )
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
            template.kind = seed_session.type
            template.is_rest_optional = seed_session.is_rest_optional
        else:
            _set(
                template,
                result,
                position=position,
                name=seed_session.name,
                focus=seed_session.focus,
                is_rest_optional=seed_session.is_rest_optional,
                kind=seed_session.type,
            )
        _version(template.items, seed_session.items, exercises, result)
        _version(template.gym_items, seed_session.gym, exercises, result)
    session.flush()

    _apply_versions(session, plan, result)

    first = templates[plan.sessions[0].slug]
    for user_id in people:
        mine = {ALL_USERS: True}  # the seed names the user itself
        if (
            session.scalar(
                select(PlanState.id).where(PlanState.user_id == user_id), execution_options=mine
            )
            is None
        ):
            session.add(PlanState(user_id=user_id, next_template_id=first.id))
            result.created += 1
        if (
            session.scalar(
                select(UserSettings.id).where(UserSettings.user_id == user_id),
                execution_options=mine,
            )
            is None
        ):
            session.add(UserSettings(user_id=user_id))
            result.created += 1

    counts = {"created": result.created, "updated": result.updated, "deleted": result.deleted}
    if result.changed:
        session.add(Event(kind="seed.applied", payload=counts))
        log.info("seed.applied", **counts)
    else:
        log.info("seed.unchanged")
    return result
