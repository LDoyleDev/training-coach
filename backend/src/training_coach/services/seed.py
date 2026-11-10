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
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from importlib.resources import files
from typing import Annotated, Literal, Self

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    FitnessTestDay,
    LadderStep,
    PlanNotice,
    PlanState,
    PlanVersion,
    SessionTemplate,
    SetLog,
    TemplateItem,
    User,
    UserSettings,
)
from training_coach.db.session import ALL_USERS
from training_coach.domain.enums import ExerciseKind, Place
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
from training_coach.domain.step_levels import Mark, StepLevel, first_fall
from training_coach.domain.stretching import Stretch
from training_coach.services.plan_rows import in_cycle
from training_coach.services.users import OWNER

log = structlog.get_logger(__name__)

SLUG = r"^[a-z0-9]+(-[a-z0-9]+)*$"
_PARK_OFFSET = 10_000
STARTING_VERSION = "Starting plan"  # a new person's first version (ADR-0073)
# Loads only a gym carries: an exercise taking one isn't done away (ADR-0086). Not dumbbells: a
# home step that takes them names them as its kit, so away passes over it, as the kit lock does.
GYM_LOADS = frozenset({LoadKit.BARBELL, LoadKit.MACHINE})


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
    # ladder step -> "Can you do ...?": a yes says the person can start at that step (G1,
    # ADR-0075); read from the bundled plan like needs. The first step needs none.
    questions: dict[str, Annotated[str, Field(min_length=1, max_length=160, pattern=r"\?$")]] = (
        Field(default_factory=dict)
    )
    # ladder step -> what carries its weight: the step takes load (ADR-0072); read from the
    # bundled plan like needs
    loads: dict[str, LoadKit] = Field(default_factory=dict)
    # ladder step -> who it is for, 1-6, and what it asks of the body (ADR-0083); stored on
    # the step and written on every run, like cues. Every step has a level unless retired.
    levels: dict[str, StepLevel] = Field(default_factory=dict)
    marks: dict[str, Annotated[list[Mark], Field(min_length=1)]] = Field(default_factory=dict)
    # A last set to failure is safe here: isolation and stable exercises (ADR-0084)
    failure_ok: bool = False
    # A lengthened-position pick, first in the picker (program-builder.md, Decided 5); read from
    # the bundled plan like needs
    lengthened: bool = False
    # Reps, seconds or minutes a set, low to high, for an exercise no session uses yet (an
    # entry exercise, ADR-0083): its questions ask for the bottom. A session item sets its own.
    range: tuple[Annotated[int, Field(ge=1)], Annotated[int, Field(ge=1)]] | None = None
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

    def _levels_and_marks(self) -> None:
        for table, named in (("levels", self.levels), ("marks", self.marks)):
            unknown = sorted(set(named) - set(self.ladder))
            if unknown:
                raise ValueError(f"{self.slug}: {table} for {unknown}, which is not in its ladder")
        missing = [step for step in self.ladder if step not in self.levels]
        if missing and not self.retired:
            raise ValueError(f"{self.slug}: no level for {missing}")
        levelled = [step for step in self.ladder if step in self.levels]
        fall = first_fall([self.levels[step] for step in levelled])
        if fall is not None:
            raise ValueError(
                f"{self.slug}: {levelled[fall]!r} is a lower level than {levelled[fall - 1]!r}; "
                "levels never fall going up a ladder"
            )
        for step, marks in self.marks.items():
            if len(set(marks)) != len(marks):
                raise ValueError(f"{self.slug}, {step!r}: a mark is listed twice")

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
        unknown = sorted(set(self.questions) - set(self.ladder))
        if unknown:
            raise ValueError(f"{self.slug}: questions for {unknown}, which is not in its ladder")
        if self.ladder[0] in self.questions:
            raise ValueError(f"{self.slug}: the first step needs no question, anyone starts there")
        unknown = sorted(set(self.loads) - set(self.ladder))
        if unknown:
            raise ValueError(f"{self.slug}: loads for {unknown}, which is not in its ladder")
        if self.loads and self.kind is not ExerciseKind.REPS:
            raise ValueError(f"{self.slug}: only an exercise counted in reps takes load")
        if self.failure_ok and self.kind is not ExerciseKind.REPS:
            raise ValueError(
                f"{self.slug}: only an exercise counted in reps has a last set to failure"
            )
        if self.range is not None and self.range[1] < self.range[0]:
            raise ValueError(f"{self.slug}: its range runs from high to low")
        self._levels_and_marks()
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


def away_problem(exercise: ExerciseSeed) -> str | None:
    """Why an exercise can't be in an away version, in words following its name; None when it
    can (``PlanSeed._away_needs_no_kit``)."""
    first = exercise.ladder[0]
    if exercise.needs.get(first) or first in exercise.loads:
        return f"'s first step {first!r} needs kit"
    if set(exercise.loads.values()) & GYM_LOADS:
        return " is gym work"
    for step in exercise.loads:
        if not exercise.needs.get(step):
            return f"'s step {step!r} takes load but names no kit"
    return None


class SessionSeed(_Strict):
    slug: str = Field(pattern=SLUG, max_length=64)
    type: Literal["strength", "conditioning", "recovery"] = "strength"
    name: str = Field(min_length=1, max_length=120)
    focus: str = Field(min_length=1, max_length=120)
    is_rest_optional: bool = False
    # The queue's rest places after it (ADR-0091): days with no session once it is done.
    rest_after: int = Field(default=0, ge=0, le=6)
    items: list[ItemSeed] = Field(min_length=1)
    # The gym version (ADR-0071); empty: done the same way at the gym.
    gym: list[ItemSeed] = Field(default_factory=list)
    # The away version, with no equipment (ADR-0086); empty: Today doesn't offer Away.
    away: list[ItemSeed] = Field(default_factory=list)

    @property
    def versions(self) -> tuple[ItemSeed, ...]:
        """Every item of every version."""
        return (*self.items, *self.gym, *self.away)

    @staticmethod
    def check_pairs(name: str, version: Sequence[ItemSeed]) -> None:
        """Each pair number marks exactly two items, next to each other."""
        numbers = [item.pair for item in version]
        for number in {n for n in numbers if n is not None}:
            where = [i for i, n in enumerate(numbers) if n == number]
            if len(where) != 2 or where[1] != where[0] + 1:
                raise ValueError(f"session {name}: pair {number} must be two neighbouring items")

    @model_validator(mode="after")
    def _pairs(self) -> Self:
        for version in (self.items, self.gym, self.away):
            self.check_pairs(self.slug, version)
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


WEEK = 7  # a starter's sessions and rest places together (ADR-0091)


class StarterSeed(_Strict):
    """A plan a new person can start on, by days a week (any-level-any-time.md S1, ADR-0073):
    its sessions in queue order, each with its rest places. It is done the same way away, as
    every bottom step needs no kit, so each session's away version is its home one."""

    slug: str = Field(pattern=SLUG, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    days: int = Field(ge=1, le=WEEK)
    sessions: list[SessionSeed] = Field(min_length=1)

    @field_validator("sessions")
    @classmethod
    def _away_as_home(cls, sessions: list[SessionSeed]) -> list[SessionSeed]:
        return [s if s.away else s.model_copy(update={"away": list(s.items)}) for s in sessions]

    @model_validator(mode="after")
    def _week(self) -> Self:
        slugs = [s.slug for s in self.sessions]
        if len(slugs) != len(set(slugs)):
            raise ValueError(f"starter {self.slug}: duplicate session slug")
        if len(self.sessions) != self.days:
            raise ValueError(f"starter {self.slug}: {self.days} days but {len(slugs)} sessions")
        week = sum(1 + s.rest_after for s in self.sessions)
        if week != WEEK:
            raise ValueError(f"starter {self.slug}: sessions and rest places make {week} days")
        return self


class GymSwapSeed(_Strict):
    """A starter exercise done as a gym exercise from one of its home steps up (S1, Decided 5):
    the item keeps its sets and pair and takes this range. ``sessions``: only in these starter
    sessions; empty, in every other."""

    exercise: str
    from_step: str = Field(min_length=1)
    gym: str
    rep_min: int = Field(ge=1)
    rep_max: int = Field(ge=1)
    sessions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _range(self) -> Self:
        if self.rep_max < self.rep_min:
            raise ValueError(f"gym swap {self.exercise} to {self.gym}: rep_max < rep_min")
        return self


class PlanSeed(_Strict):
    exercises: list[ExerciseSeed] = Field(min_length=1)
    # The owner's cycle (ADR-0073): what the owner starts on and the import follows.
    sessions: list[SessionSeed] = Field(min_length=1)
    # What everyone else starts on: ``new_people`` names the one until setup picks by days.
    starters: list[StarterSeed] = Field(default_factory=list)
    new_people: str | None = None
    # The starters' gym versions, written per person from where they are placed (S1).
    gym_swaps: list[GymSwapSeed] = Field(default_factory=list)
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
        starters = [s.slug for s in self.starters]
        if len(starters) != len(set(starters)):
            raise ValueError("duplicate starter slug")
        if self.new_people is not None and self.new_people not in starters:
            raise ValueError(f"new_people names {self.new_people}, which is not a starter")
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
        used = {i.exercise for s in self.every_session for i in s.versions}
        used |= {s.gym for s in self.gym_swaps}
        ranged = sorted(e.slug for e in self.exercises if e.range is not None and e.slug in used)
        if ranged:
            raise ValueError(f"{ranged} have a range, but a session sets theirs")
        for session in self.every_session:
            for item in session.versions:
                if item.exercise not in known:
                    raise ValueError(f"session {session.slug}: unknown exercise {item.exercise}")
                if item.exercise in retired:
                    raise ValueError(
                        f"session {session.slug} uses {item.exercise}, which is retired; "
                        "un-retire it or take it out of the session"
                    )
        self._away_needs_no_kit()
        self._gym_swaps()
        return self

    @property
    def every_session(self) -> tuple[SessionSeed, ...]:
        """The owner's sessions and every starter's: the catalogue must hold what each uses."""
        return (*self.sessions, *(s for starter in self.starters for s in starter.sessions))

    def starter_for(self, user_id: int) -> StarterSeed | None:
        """The starter a person with no plan starts on: ``new_people``'s for anyone but the
        owner, who starts on their cycle (as does everyone while there is no starter)."""
        if user_id == OWNER:
            return None
        return next((s for s in self.starters if s.slug == self.new_people), None)

    def first_sessions(self, user_id: int) -> list[SessionSeed]:
        found = self.starter_for(user_id)
        return self.sessions if found is None else found.sessions

    def _away_needs_no_kit(self) -> None:
        """An away version (ADR-0086) is done with no equipment: each exercise's first step
        needs no kit and takes no load, so there is always a step to train; none of its steps
        takes a gym load (a barbell or a machine); and a step that takes load names its kit, so
        the kit lock passes over it away."""
        exercises = {e.slug: e for e in self.exercises}
        for session in self.every_session:
            for item in session.away:
                problem = away_problem(exercises[item.exercise])
                if problem:
                    raise ValueError(f"session {session.slug}: away, {item.exercise}{problem}")

    def _gym_swaps(self) -> None:
        """A swap turns a starter exercise into a gym exercise (ADR-0072: its last step takes
        load and no step names kit, so one step, or the 45° back extension's bodyweight then a
        plate) from a home step at or above the gym exercise's level (S1), in sessions that use
        it; each exercise has at most one swap for every session, and one per session."""
        exercises = {e.slug: e for e in self.exercises}
        starter = {s.slug: s for st in self.starters for s in st.sessions}
        general: set[str] = set()
        named: set[tuple[str, str]] = set()
        for swap in self.gym_swaps:
            where = f"gym swap {swap.exercise} to {swap.gym}"
            home, gym = exercises.get(swap.exercise), exercises.get(swap.gym)
            if home is None or gym is None or home.retired or gym.retired:
                raise ValueError(f"{where}: unknown exercise")
            if swap.from_step not in home.ladder:
                raise ValueError(f"{where}: {swap.from_step!r} is not in its ladder")
            if gym.ladder[-1] not in gym.loads or any(gym.needs.values()):
                raise ValueError(f"{where}: {swap.gym} is not a gym exercise")
            if home.levels[swap.from_step] < gym.levels[gym.ladder[0]]:
                raise ValueError(f"{where}: {swap.from_step!r} is below {gym.name}'s level")
            using = {
                slug for slug, s in starter.items() if home.slug in {i.exercise for i in s.items}
            }
            if not using:
                raise ValueError(f"{where}: no starter uses {home.slug}")
            if not swap.sessions:
                if home.slug in general:
                    raise ValueError(f"{where}: {home.slug} has two swaps for every session")
                general.add(home.slug)
            for slug in swap.sessions:
                if slug not in using:
                    raise ValueError(f"{where}: {slug} is no starter session with it")
                if (home.slug, slug) in named:
                    raise ValueError(f"{where}: {slug} has two swaps for it")
                named.add((home.slug, slug))


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


def _stored_items_preflight(session: Session, plan: PlanSeed) -> None:
    """The catalogue must still hold what anyone's plan uses: the checks ``PlanSeed`` makes of
    its own sessions, made of everyone's stored ones (ADR-0073)."""
    catalogue = {e.slug: e for e in plan.exercises}
    stored = session.execute(
        select(Exercise.slug, TemplateItem.place)
        .join(TemplateItem, TemplateItem.exercise_id == Exercise.id)
        .distinct(),
        execution_options={ALL_USERS: True},
    )
    for slug, place in stored:
        exercise = catalogue.get(slug)
        if exercise is None:
            raise SeedError(f"{slug} is in someone's plan, so it must stay in plan.toml")
        if exercise.retired:
            raise SeedError(f"{slug} is in someone's plan, so it can't be retired")
        problem = away_problem(exercise) if place == Place.AWAY else None
        if problem:
            raise SeedError(f"{slug} is in someone's away version, and {slug}{problem}")


def _tests_preflight(session: Session, plan: PlanSeed) -> None:
    """A test with results stays in the plan: its results name it."""
    kept = {t.slug for t in plan.tests}
    days = session.scalars(select(FitnessTestDay), execution_options={ALL_USERS: True})
    recorded = {r["test"] for day in days for r in day.results}
    missing = sorted(recorded - kept)
    if missing:
        raise SeedError(f"tests {missing} have results but are not in plan.toml; keep them there")


def _set(obj: object, result: SeedResult, **values: object) -> None:
    """Assign attributes, counting an update only when something actually changes."""
    dirty = False
    for key, value in values.items():
        if getattr(obj, key) != value:
            setattr(obj, key, value)
            dirty = True
    if dirty:
        result.updated += 1


def sync_version(
    user_id: int,
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
            items.append(TemplateItem(user_id=user_id, position=position, **values))
            result.created += 1
        else:
            _set(item, result, **values)
    for position, item in found.items():
        if position >= len(seeds):
            items.remove(item)  # delete-orphan: removed from the plan
            result.deleted += 1


def _tell_people(session: Session, changes: dict[str, list[str]]) -> None:
    """A notice for each person whose plan has a changed exercise, in any version (ADR-0087). It
    runs before anyone new starts: a plan made after the change has nothing to be told."""
    if not changes:
        return
    using = session.execute(
        select(TemplateItem.user_id, Exercise.slug)
        .join(Exercise, Exercise.id == TemplateItem.exercise_id)
        .where(Exercise.slug.in_(changes))
        .distinct()
        .order_by(TemplateItem.user_id, Exercise.slug),
        execution_options={ALL_USERS: True},
    )
    for user_id, slug in using.all():
        session.add_all(PlanNotice(user_id=user_id, text=text) for text in changes[slug])


def sync_sessions(
    session: Session,
    sessions: Sequence[SessionSeed],
    user_id: int,
    exercises: dict[str, Exercise],
    result: SeedResult,
) -> None:
    """Make this person's sessions in the cycle match ``sessions``: a new one's items, or an
    existing one's by position. Items removed from a session are deleted (nothing else
    references them). Retired sessions are left as they are, parked (ADR-0093); one of
    their slugs in ``sessions`` raises, since putting a session back isn't built yet."""
    wanted = {s.slug: i for i, s in enumerate(sessions)}
    retired = session.scalars(
        select(SessionTemplate.slug)
        .where(SessionTemplate.user_id == user_id, ~in_cycle(), SessionTemplate.slug.in_(wanted))
        .order_by(SessionTemplate.slug),
        execution_options={ALL_USERS: True},
    ).all()
    if retired:
        raise SeedError(f"{', '.join(retired)} retired from this plan, so can't be made again")
    templates = {
        t.slug: t
        for t in session.scalars(
            select(SessionTemplate).where(SessionTemplate.user_id == user_id, in_cycle()),
            execution_options={ALL_USERS: True},
        )
    }
    current = {t.slug: t.position for t in templates.values()}
    if current != {slug: wanted[slug] for slug in current}:
        # Reordering: park existing positions out of the way so the unique index never
        # sees two sessions on one position mid-update. New sessions always get positions
        # after the existing ones' final positions, so they cannot collide.
        for existing in templates.values():
            existing.position += _PARK_OFFSET
        session.flush()
    for position, seed_session in enumerate(sessions):
        template = templates.get(seed_session.slug)
        if template is None:
            template = SessionTemplate(user_id=user_id, slug=seed_session.slug, position=position)
            session.add(template)
            templates[seed_session.slug] = template
            result.created += 1
            template.name, template.focus = seed_session.name, seed_session.focus
            template.kind = seed_session.type
            template.is_rest_optional = seed_session.is_rest_optional
            template.rest_after = seed_session.rest_after
        else:
            _set(
                template,
                result,
                position=position,
                name=seed_session.name,
                focus=seed_session.focus,
                is_rest_optional=seed_session.is_rest_optional,
                kind=seed_session.type,
                rest_after=seed_session.rest_after,
            )
        sync_version(user_id, template.items, seed_session.items, exercises, result)
        sync_version(user_id, template.gym_items, seed_session.gym, exercises, result)
        sync_version(user_id, template.away_items, seed_session.away, exercises, result)
    session.flush()


def _start_plan(
    session: Session,
    plan: PlanSeed,
    user_id: int,
    exercises: dict[str, Exercise],
    result: SeedResult,
) -> None:
    """A person with no sessions (new, or erased) gets a starter: the owner the 7-day cycle,
    anyone else ``new_people``'s (ADR-0073). ``plan.toml``'s versions are the owner's history,
    so they get one."""
    sync_sessions(session, plan.first_sessions(user_id), user_id, exercises, result)
    if plan.versions:
        since = max(v.since for v in plan.versions)
        session.add(PlanVersion(user_id=user_id, since=since, name=STARTING_VERSION))
        result.created += 1
    session.flush()


def apply_seed(session: Session, plan: PlanSeed) -> SeedResult:
    """Upsert the catalogue, and start anyone who has no plan yet. It never changes the sessions
    of a person who has them (ADR-0073). The caller owns the transaction (commit / rollback).

    Raises ``SeedError`` before changing anything if the plan would shorten a ladder, rename a
    ladder step that history uses without a ``renames`` entry, or take away what someone's plan
    uses: all would remap or orphan logged history.
    """
    result = SeedResult()

    exercises = {e.slug: e for e in session.scalars(select(Exercise))}
    _preflight(session, plan, exercises)
    _stored_items_preflight(session, plan)
    _tests_preflight(session, plan)
    changes: dict[str, list[str]] = {}
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
            exercise.failure_ok = seed.failure_ok
        else:
            if exercise.name != seed.name:
                changes.setdefault(seed.slug, []).append(
                    f"{exercise.name} is now called {seed.name}."
                )
            _set(
                exercise,
                result,
                name=seed.name,
                kind=seed.kind.value,
                aliases=list(seed.aliases),
                retired=seed.retired,
                per_side=seed.per_side,
                failure_ok=seed.failure_ok,
            )
        steps = {step.position: step for step in exercise.ladder}
        had_steps = bool(steps)
        for position, name in enumerate(seed.ladder):
            step = steps.get(position)
            facts = {
                "cue": seed.cues.get(name),
                "level": seed.levels.get(name),
                "marks": [mark.value for mark in seed.marks.get(name, [])],
            }
            if step is None:
                exercise.ladder.append(LadderStep(position=position, name=name, **facts))
                result.created += 1
                if had_steps:
                    changes.setdefault(seed.slug, []).append(f'{seed.name}: a new level, "{name}".')
            else:
                if step.name != name:
                    changes.setdefault(seed.slug, []).append(
                        f'{seed.name}: "{step.name}" is now "{name}".'
                    )
                _set(step, result, name=name, **facts)
    session.flush()
    _tell_people(session, changes)

    for user_id in list(session.scalars(select(User.id).order_by(User.id))):
        start_person(session, plan, user_id, exercises, result)

    counts = {"created": result.created, "updated": result.updated, "deleted": result.deleted}
    if result.changed:
        session.add(Event(kind="seed.applied", payload=counts))
        log.info("seed.applied", **counts)
    else:
        log.info("seed.unchanged")
    return result


def start_person(
    session: Session,
    plan: PlanSeed,
    user_id: int,
    exercises: dict[str, Exercise],
    result: SeedResult,
) -> None:
    """Whatever this person lacks of what everyone starts with: a place on every ladder (its
    bottom, for anyone but the owner once there are starters), a plan (ADR-0073), a place in its
    queue and their settings. Run by
    every seed for everyone, and when someone joins (ADR-0059). In an unbound session: every
    query names the user."""
    mine = {ALL_USERS: True}  # the seed names the user itself
    started = set(
        session.scalars(
            select(ExerciseState.exercise_id).where(ExerciseState.user_id == user_id),
            execution_options=mine,
        )
    )
    # Everyone but the owner starts every exercise at the bottom of its ladder, setup moving them
    # up (any-level S1, B5), an exercise added later too, whatever plan they have by then;
    # ``start`` is where the owner's cycle starts each one.
    bottom = plan.starter_for(user_id) is not None
    for seed in plan.exercises:
        exercise = exercises[seed.slug]
        if exercise.id not in started:
            at = 0 if bottom else seed.start
            start_step = next(s for s in exercise.ladder if s.position == at)
            session.add(
                ExerciseState(
                    user_id=user_id, exercise_id=exercise.id, ladder_step_id=start_step.id
                )
            )
            result.created += 1
    sessions = select(SessionTemplate.id).where(SessionTemplate.user_id == user_id)
    if session.scalars(sessions, execution_options=mine).first() is None:
        _start_plan(session, plan, user_id, exercises, result)
    if (
        session.scalar(
            select(PlanState.id).where(PlanState.user_id == user_id), execution_options=mine
        )
        is None
    ):
        first = session.scalars(
            sessions.where(in_cycle()).order_by(SessionTemplate.position), execution_options=mine
        ).first()
        session.add(PlanState(user_id=user_id, next_template_id=first))
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
