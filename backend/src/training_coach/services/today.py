"""Today's session and the week ahead, read from the database (ADR-0006, ADR-0014, ADR-0016).

Returns plain data; the bot formats it. ``None`` means there is no plan in the database (for
example a failed seed on a fresh install, ADR-0015), which callers must tell the user about.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import (
    SessionTemplate,
    TemplateItem,
    Workout,
)
from training_coach.domain.blocks import Block
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.queue import ADVANCING, Position, upcoming
from training_coach.domain.targets import targets
from training_coach.services import blocks, users
from training_coach.services.progress import sessions_at_step
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


@dataclass(frozen=True)
class SessionPlan:
    template_id: int
    name: str
    focus: str
    optional: bool
    items: tuple[ItemPlan, ...]
    kind: str = "strength"  # strength | conditioning | recovery (plan.toml)


@dataclass(frozen=True)
class Today:
    session: SessionPlan
    logged_today: tuple[str, ...]  # "Legs (done)", one per workout already logged today
    block: Block | None = None  # the training block, when blocks are on (ADR-0028)


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


def _item_plan(session: Session, item: TemplateItem, strength: bool) -> ItemPlan:
    """One exercise: its step, cue and targets, under the strength prescription if it applies
    (ADR-0028), with targets from the matching block's history (ADR-0027)."""
    plan = blocks.assign(session, item, strength)
    history = [
        v
        for _, v in sessions_at_step(
            session, item.exercise_id, plan.step.id, item.per_side, plan.history
        )
    ]
    return ItemPlan(
        exercise=item.exercise.name,
        kind=ExerciseKind(item.exercise.kind),
        step=plan.step.name,
        cue=plan.cue,
        summary=summary(item.exercise.slug),
        slug=item.exercise.slug,
        per_side=item.per_side,
        targets=targets(plan.prescription, history),
        pair=item.pair,
        baseline=not history,
    )


def session_plan(
    session: Session, template_id: int, block: Block | None = None
) -> SessionPlan | None:
    """One session of the plan with today's ladder steps and targets, in ``block``."""
    template = session.scalar(
        select(SessionTemplate)
        .where(SessionTemplate.id == template_id)
        .options(selectinload(SessionTemplate.items).selectinload(TemplateItem.exercise))
    )
    if template is None:
        return None
    return SessionPlan(
        template_id=template.id,
        name=template.name,
        focus=template.focus,
        optional=template.is_rest_optional,
        items=tuple(
            _item_plan(session, item, blocks.strength_applies(block, template.kind))
            for item in template.items
        ),
        kind=template.kind,
    )


def today(session: Session, on: date, tz: ZoneInfo | None = None) -> Today | None:
    """The session at the pointer, with targets, and what has been logged on ``on``; with
    ``tz``, also the training block ``on`` falls in."""
    current = position(session)
    block = blocks.current(session, on, tz) if tz is not None else None
    plan = session_plan(session, current.pointer, block) if current is not None else None
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
    )


def week(session: Session, on: date, days: int = 7) -> list[Day] | None:
    """The next ``days`` sessions, dated as if each is done on its day (ADR-0006).

    Starts tomorrow when today's planned session is already done or rested.
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
    start = on + timedelta(days=1) if advanced_today is not None else on
    names = {t.id: t.name for t in order}
    return [
        Day(date=start + timedelta(days=i), session=names[template_id])
        for i, template_id in enumerate(upcoming(ids, current, days))
    ]
