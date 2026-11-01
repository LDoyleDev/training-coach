"""Today's session and the week ahead, read from the database (ADR-0006, ADR-0014, ADR-0016).

Returns plain data; the bot formats it. ``None`` means there is no plan in the database (for
example a failed seed on a fresh install, ADR-0015), which callers must tell the user about.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import (
    FitnessTestDay,
    LadderStep,
    SessionProgress,
    SessionTemplate,
    TemplateItem,
    Workout,
)
from training_coach.domain.blocks import Block
from training_coach.domain.enums import ExerciseKind, Place
from training_coach.domain.kit import Item
from training_coach.domain.load import (
    DEFAULTS,
    Increments,
    Load,
    carried,
    owned_weights,
    progressed,
    top_weight,
)
from training_coach.domain.muscles import Muscle, Part, ranked
from training_coach.domain.places import choices, day_place
from training_coach.domain.queue import ADVANCING, Position, advance
from training_coach.domain.retests import PastTest
from training_coach.domain.targets import Pace, targets
from training_coach.services import blocks, equipment, retests, user_settings, users
from training_coach.services.blocks import load_kit
from training_coach.services.progress import last_loads, planned_sets, sessions_at_step
from training_coach.services.seed import bundled_plan


@dataclass(frozen=True)
class ItemPlan:
    exercise: str
    kind: ExerciseKind
    step: str
    cue: str | None
    per_side: bool
    targets: tuple[int, ...]  # one per set, in order
    pair: int | None = None  # done alternately with the other item of this pair (#97)
    summary: str | None = None  # how to do the exercise (#116); cue: this step's detail
    slug: str = ""  # the exercise, for logging what the guided session records (#117)
    # No history at this step yet: this session finds the level the targets grow from
    # (ADR-0027, ADR-0034).
    baseline: bool = False
    # What it works, from the catalogue (ADR-0064): the most worked first; empty for an
    # exercise that trains only qualities (cardio, mobility, a chin tuck).
    muscles: tuple[tuple[Muscle, float], ...] = ()
    parts: tuple[Part, ...] = ()
    # A loaded step (ADR-0072): its kit, increment and each set's starting weight.
    load: Load | None = None
    step_id: int = 0  # the ladder step trained, for changing it in the session (ADR-0080)
    # Away, below the person's level: their step needs kit, so today's needs none (ADR-0086).
    no_kit: bool = False


@dataclass(frozen=True)
class Worked:
    muscles: tuple[tuple[Muscle, float], ...] = ()
    parts: tuple[Part, ...] = ()


@dataclass(frozen=True)
class SessionPlan:
    template_id: int
    name: str
    focus: str
    optional: bool
    items: tuple[ItemPlan, ...]
    kind: str = "strength"  # strength | conditioning | recovery (plan.toml)
    slug: str = ""  # the session template's, e.g. "hiit"
    # Where it is done, and so which version (ADR-0071); ``places``: what Today's switch offers
    # (Home | Gym, and Away with an away version, ADR-0086), one place when there is no choice.
    place: Place = Place.HOME
    places: tuple[Place, ...] = (Place.HOME,)

    @property
    def switch(self) -> bool:
        """Today shows the switch: there is a place to choose."""
        return len(self.places) > 1


@dataclass(frozen=True)
class Today:
    session: SessionPlan
    logged_today: tuple[str, ...]  # "Legs (done)", one per workout already logged today
    block: Block | None = None  # the training block, when blocks are on (ADR-0028)
    # A test day due today (ADR-0038): it comes first, and the session waits a day.
    test_day: retests.TestDayDue | None = None


@dataclass(frozen=True)
class Day:
    date: date
    session: str


def _order(session: Session) -> list[SessionTemplate]:
    query = select(SessionTemplate).order_by(SessionTemplate.position)
    return list(session.scalars(query))


def position(session: Session) -> Position | None:
    """The queue position, or None when there is no plan (or it points nowhere)."""
    state = users.plan_state(session)
    if state is None or state.next_template_id is None:
        return None
    # Queued ids have no foreign key; drop any whose session has left the plan.
    known = set(session.scalars(select(SessionTemplate.id)))
    return Position(state.next_template_id, tuple(t for t in state.queued if t in known))


def summary(slug: str) -> str | None:
    """An exercise's how-to from the bundled plan (#116), or None for one it doesn't know."""
    return _summaries().get(slug)


@lru_cache(maxsize=1)
def _summaries() -> dict[str, str]:
    return {e.slug: e.summary for e in bundled_plan().exercises if e.summary}


def worked(slug: str) -> Worked:
    """The muscles an exercise works and the parts it reaches, from the bundled plan like the
    summary; nothing for an exercise it doesn't know."""
    return _worked().get(slug, Worked())


@lru_cache(maxsize=1)
def _worked() -> dict[str, Worked]:
    return {
        e.slug: Worked(tuple(ranked(e.muscles)), tuple(e.parts)) for e in bundled_plan().exercises
    }


def _item_plan(
    session: Session,
    item: TemplateItem,
    strength: bool,
    pace: Pace,
    chosen: int | None = None,
    increments: Increments = DEFAULTS,
    home_kit: Sequence[Item] | None = None,
    at_gym: bool = False,
    away: bool = False,
) -> ItemPlan:
    """One exercise: its step, cue and targets, under the strength prescription if it applies
    (ADR-0028), with targets from the matching block's history (ADR-0027) at the person's
    ``pace`` (ADR-0057). ``chosen``: a step of its ladder picked for today (ADR-0080). A loaded
    step moves by the person's own ``increments``, or on a home day through the weights in
    ``home_kit`` (ADR-0072). ``away``: steps that need kit give way to ones that don't
    (ADR-0086)."""
    step = session.get(LadderStep, chosen) if chosen is not None else None
    plan = blocks.assign(
        session,
        item,
        strength,
        step if step is not None and step.exercise_id == item.exercise_id else None,
        at_gym=at_gym,
        away=away,
    )
    kit = load_kit(item.exercise.slug, plan.step.name)
    last = last_loads(session, item.exercise_id, plan.step.id, plan.history) if kit else []
    # A loaded step's targets come from the sessions at the weight it last used: a heavier
    # weight starts from its own baseline, as a new ladder step does (ADR-0072).
    weight = top_weight(last)
    done = sessions_at_step(
        session, item.exercise_id, plan.step.id, item.per_side, plan.history, weight
    )
    history = [v for _, v in done]
    # Sets a shorter day didn't plan are neither missed nor replayed (ADR-0084).
    planned = planned_sets(session, item.exercise.slug, [w for w, _ in done])
    load = None
    if kit is not None:
        owned = owned_weights(kit, home_kit, increments)
        load = carried(kit, plan.prescription.sets, last, increments, owned)
        load = progressed(load, plan.prescription, history[0] if history else None, last)
    found = worked(item.exercise.slug)
    return ItemPlan(
        exercise=item.exercise.name,
        kind=ExerciseKind(item.exercise.kind),
        step=plan.step.name,
        cue=plan.cue,
        summary=summary(item.exercise.slug),
        slug=item.exercise.slug,
        per_side=item.per_side,
        targets=targets(plan.prescription, history, pace, planned),
        pair=item.pair,
        baseline=not history,
        muscles=found.muscles,
        parts=found.parts,
        load=load,
        step_id=plan.step.id,
        no_kit=plan.no_kit,
    )


def away_on(session: Session, on: date) -> bool:
    """Whether ``on`` was chosen as an away day on Today's switch (ADR-0086): kept on that day's
    guided-session progress, never as the place Today starts at."""
    place = session.scalar(select(SessionProgress.place).where(SessionProgress.local_date == on))
    return place == Place.AWAY


def session_plan(
    session: Session,
    template_id: int,
    block: Block | None = None,
    steps: Mapping[str, int] | None = None,
    place: Place | None = None,
    *,
    on: date | None = None,
) -> SessionPlan | None:
    """One session of the plan with today's ladder steps and targets, in ``block``: its
    version for ``place``, by default the day's (ADR-0071), so the bot's messages, a typed
    log and the guided session all see the same exercises. ``on``: the day it is for, away
    when that day was chosen as away (ADR-0086). ``steps`` holds levels chosen for today in the
    guided session, by exercise slug (ADR-0080)."""
    template = session.scalar(
        select(SessionTemplate)
        .where(SessionTemplate.id == template_id)
        .options(
            selectinload(SessionTemplate.items).selectinload(TemplateItem.exercise),
            selectinload(SessionTemplate.gym_items).selectinload(TemplateItem.exercise),
            selectinload(SessionTemplate.away_items).selectinload(TemplateItem.exercise),
        )
    )
    if template is None:
        return None
    prefs = user_settings.load(session)
    pace = prefs.pace
    if place is not None:
        at = place
    elif on is not None and away_on(session, on):
        at = Place.AWAY
    else:
        at = day_place(prefs.places, prefs.place)
    done_at = template.done_at(at)  # the version's place, not only the one asked for
    # At home, a loaded kit the person lists goes up by the weights they own (ADR-0072).
    home_kit = equipment.kit(session) if done_at is Place.HOME else None
    return SessionPlan(
        template_id=template.id,
        name=template.name,
        focus=template.focus,
        optional=template.is_rest_optional,
        items=tuple(
            _item_plan(
                session,
                item,
                blocks.strength_applies(block, template.kind),
                pace,
                (steps or {}).get(item.exercise.slug),
                prefs.increments,
                home_kit,
                done_at is Place.GYM,
                done_at is Place.AWAY,
            )
            for item in template.version(at)
        ),
        kind=template.kind,
        slug=template.slug,
        place=done_at,
        places=choices(prefs.places, bool(template.gym_items), bool(template.away_items)),
    )


def today(session: Session, on: date, tz: ZoneInfo | None = None) -> Today | None:
    """The session at the pointer, with targets, and what has been logged on ``on``; with
    ``tz``, also the training block ``on`` falls in."""
    current = position(session)
    block = blocks.current(session, on, tz) if tz is not None else None
    plan = session_plan(session, current.pointer, block, on=on) if current is not None else None
    if plan is None:
        return None
    names = {t.id: t.name for t in _order(session)}
    logged = session.scalars(
        select(Workout).where(Workout.local_date == on).order_by(Workout.created_at)
    )
    return Today(
        session=plan,
        logged_today=tuple(
            f"{names[w.template_id] if w.template_id else 'Extra'} ({w.status})" for w in logged
        ),
        block=block,
        test_day=retests.due(session, on, tz) if tz is not None else None,
    )


def week(session: Session, on: date, days: int = 7, tz: ZoneInfo | None = None) -> list[Day] | None:
    """The next ``days`` sessions, dated as if each is done on its day (ADR-0006); with
    ``tz``, test days that fall due take their day and the sessions wait (ADR-0038).

    Starts tomorrow when today's planned session is already done or rested, or a test day was
    saved today.
    """
    current = position(session)
    order = _order(session)
    ids = [t.id for t in order]
    if current is None or current.pointer not in ids:
        return None
    advanced_today = session.scalar(
        select(Workout.id).where(
            Workout.local_date == on,
            Workout.template_id.is_not(None),
            Workout.status.in_(ADVANCING),
        )
    )
    tested_today = session.scalar(
        select(FitnessTestDay.id).where(FitnessTestDay.local_date == on).limit(1)
    )
    done_today = advanced_today is not None or tested_today is not None
    start = on + timedelta(days=1) if done_today else on
    names = {t.id: t.name for t in order}
    planned = retests.done(session) if tz is not None else []
    result: list[Day] = []
    for n in range(days):
        day = start + timedelta(days=n)
        test = retests.due(session, day, tz, planned) if tz is not None else None
        if test is not None:
            result.append(Day(date=day, session=test.name))
            planned.append(PastTest(day, test.day))  # as if done on its day
            continue
        result.append(Day(date=day, session=names[current.pointer]))
        current = advance(ids, current)
    return result
