"""What the walk-through shows before Save (ADR-0092): who it is for, its 13 ladders with what
each step asks, and the plan the person's choices would make, trimmed to their minutes and count,
with its week and its body map. Read-only: nothing here writes, so the owner's try-out sees every
screen and keeps nothing."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, ExerciseState, LadderStep
from training_coach.db.session import bound_user
from training_coach.domain import coverage as domain
from training_coach.domain.enums import Place, Places
from training_coach.domain.walkthrough import landing
from training_coach.services import guided, gym_version, users, walkthrough
from training_coach.services.coverage import plan_coverage, trained_steps
from training_coach.services.plan_edit import ItemEdit
from training_coach.services.plan_rows import PlannedItem, PlannedSession
from training_coach.services.seed import ExerciseSeed, PlanSeed
from training_coach.services.today import ItemPlan
from training_coach.services.walkthrough import Setup

# Who the walk-through is for; GET /api/walkthrough and Home both answer with it.
Who = Literal["member", "owner_try_out", "done", "closed"]
MEMBER: Final = "member"
OWNER_TRY_OUT: Final = "owner_try_out"
DONE: Final = "done"
CLOSED: Final = "closed"


def who(session: Session) -> Who:
    """Who the walk-through is for: the owner only as a try-out; a member until their first
    workout (``CLOSED`` after it), ``DONE`` once saved (it can be run again until then)."""
    if bound_user(session) == users.OWNER:
        return OWNER_TRY_OUT
    if walkthrough.closed(session):
        return CLOSED
    found = users.settings_row(session)
    return DONE if found is not None and found.set_up_on is not None else MEMBER


@dataclass(frozen=True)
class Step:
    id: int
    position: int
    name: str
    level: int | None
    question: str | None  # "Can you do ...?"; None at the bottom, where anyone starts
    cue: str | None
    needs: tuple[str, ...]  # the catalogue's: "kettlebell:8", "pull-up bar"
    marks: tuple[str, ...]  # "floor", "kneeling", "balance" ...


@dataclass(frozen=True)
class Ladder:
    slug: str
    name: str
    on: int | None  # the step id the person is on now
    steps: tuple[Step, ...]


def ladders(session: Session, plan: PlanSeed) -> list[Ladder]:
    """The walk-through's 13 ladders, in the order it asks them, each step with what it asks."""
    seeds = {e.slug: e for e in plan.exercises}
    slugs = walkthrough.ladders(plan)
    rows = {e.slug: e for e in session.scalars(select(Exercise).where(Exercise.slug.in_(slugs)))}
    on = dict(
        session.execute(select(ExerciseState.exercise_id, ExerciseState.ladder_step_id)).all()
    )
    return [
        Ladder(
            slug,
            rows[slug].name,
            on.get(rows[slug].id),
            tuple(_step(s, seeds[slug]) for s in rows[slug].ladder),
        )
        for slug in slugs
        if slug in rows and slug in seeds
    ]


def _step(step: LadderStep, seed: ExerciseSeed) -> Step:
    return Step(
        step.id,
        step.position,
        step.name,
        step.level,
        seed.questions.get(step.name),
        step.cue,
        tuple(seed.needs.get(step.name, [])),
        tuple(step.marks),
    )


# ------------------------------------------------------------------------------- the preview


@dataclass(frozen=True)
class FittedItem:
    exercise: str  # slug
    name: str
    step: str  # the step it is done at
    sets: int  # as planned
    kept: int  # after the trim; 0: dropped
    rep_min: int
    rep_max: int
    per_side: bool
    pair: int | None


@dataclass(frozen=True)
class Fitted:
    """One version of a session as it would run: trimmed to the minutes and count."""

    place: Place
    items: tuple[FittedItem, ...]
    minutes: int  # about how long, warm-up included, after the trim
    fits: bool  # within the minutes per session (always, as planned)
    dropped: tuple[str, ...]  # the exercises the trim drops, in the order they go


@dataclass(frozen=True)
class FittedSession:
    slug: str
    name: str
    focus: str
    rest_after: int
    on: date  # the day it first lands
    home: Fitted
    gym: Fitted | None  # None: done the same way at the gym, or not trained there


@dataclass(frozen=True)
class Preview:
    sessions: tuple[FittedSession, ...]
    week: tuple[tuple[date, str | None], ...]  # seven days from the start: a session's slug or rest
    coverage: tuple[tuple[Place, domain.Coverage], ...]  # home, gym, or both at both


def preview(session: Session, plan: PlanSeed, setup: Setup, today: date) -> Preview | str:
    """The plan ``setup`` would save, or why it can't be, in words; saves nothing."""
    starter = walkthrough.checked(session, plan, setup, today)
    if isinstance(starter, str):
        return starter
    catalogue = {e.slug: e for e in plan.exercises}
    picked = session.execute(
        select(Exercise.slug, LadderStep.name, LadderStep.position)
        .join(LadderStep, LadderStep.exercise_id == Exercise.id)
        .where(LadderStep.id.in_(list(setup.steps.values())))
    ).all()
    steps = {**trained_steps(session), **{slug: name for slug, name, _ in picked}}
    positions = {**gym_version.placed(session), **{slug: at for slug, _, at in picked}}
    swaps = gym_version.swaps(plan)
    days = landing(setup.starts_on, [s.rest_after for s in starter.sessions])
    fitted, planned = [], []
    for position, (seed, on) in enumerate(zip(starter.sessions, days, strict=True)):
        home = tuple(
            ItemEdit(**i.model_dump()) for i in walkthrough.without(seed.items, setup.left_out)
        )
        gym = (
            ()
            if setup.places is Places.HOME
            else gym_version.version(swaps, seed.slug, home, positions)
        )
        at_home = _fit(home, Place.HOME, seed.type, setup, catalogue, steps)
        at_gym = (
            _fit(gym, Place.GYM, seed.type, setup, catalogue, steps)
            if gym and gym != home
            else None
        )
        fitted.append(
            FittedSession(seed.slug, seed.name, seed.focus, seed.rest_after, on, at_home, at_gym)
        )
        planned.append(
            PlannedSession(
                position,
                seed.slug,
                seed.name,
                seed.focus,
                seed.type,
                seed.is_rest_optional,
                _counted(at_home),
                _counted(at_gym) if at_gym is not None else (),
                seed.rest_after,
            )
        )
    landed = {on: s.slug for s, on in zip(starter.sessions, days, strict=True)}
    week = tuple(
        (day, landed.get(day)) for day in (setup.starts_on + timedelta(days=k) for k in range(7))
    )
    places = {Places.HOME: (Place.HOME,), Places.GYM: (Place.GYM,)}.get(
        setup.places, (Place.HOME, Place.GYM)
    )
    maps = tuple((p, plan_coverage(session, p, sessions=planned, steps=steps)) for p in places)
    return Preview(tuple(fitted), week, maps)


def _fit(
    items: Sequence[ItemEdit],
    place: Place,
    kind: str,
    setup: Setup,
    catalogue: Mapping[str, ExerciseSeed],
    steps: Mapping[str, str],
) -> Fitted:
    """``items`` as they would run, trimmed to the minutes and count the person chose."""
    plans = tuple(
        ItemPlan(
            exercise=catalogue[i.exercise].name,
            kind=catalogue[i.exercise].kind,
            step=steps.get(i.exercise, catalogue[i.exercise].ladder[0]),
            cue=None,
            per_side=i.per_side,
            targets=(i.rep_min,) * i.sets,  # where a new step starts
            pair=i.pair,
            slug=i.exercise,
        )
        for i in items
    )
    trimmed = guided.fitted(plans, kind, setup.minutes, setup.exercises)
    kept = trimmed.sets if trimmed is not None else tuple(i.sets for i in items)
    minutes = (
        trimmed.minutes
        if trimmed is not None
        else guided.planned_minutes(plans, warm_up=kind == "strength")
    )
    return Fitted(
        place,
        tuple(
            FittedItem(
                i.exercise, p.exercise, p.step, i.sets, n, i.rep_min, i.rep_max, i.per_side, i.pair
            )
            for i, p, n in zip(items, plans, kept, strict=True)
        ),
        minutes,
        trimmed is None or trimmed.fits,
        tuple(plans[i].exercise for i in (trimmed.dropped if trimmed is not None else ())),
    )


def _counted(fitted: Fitted) -> tuple[PlannedItem, ...]:
    """What the body map counts of a version: the sets the trim keeps."""
    return tuple(
        PlannedItem(i.exercise, i.kept, i.rep_min, i.rep_max, i.per_side, i.pair)
        for i in fitted.items
        if i.kept
    )
