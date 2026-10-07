"""Today's session and the week ahead, read from the database (ADR-0006, ADR-0014, ADR-0016).

Returns plain data; the bot formats it. ``None`` means there is no plan in the database (for
example a failed seed on a fresh install, ADR-0015), which callers must tell the user about.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import (
    LadderStep,
    SessionTemplate,
    TemplateItem,
    Workout,
)
from training_coach.domain.blocks import Block
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.queue import ADVANCING, Position, upcoming
from training_coach.domain.targets import Prescription, targets
from training_coach.services import blocks, users
from training_coach.services.progress import sessions_at_step


@dataclass(frozen=True)
class ItemPlan:
    exercise: str
    kind: ExerciseKind
    step: str
    cue: str | None
    per_side: bool
    targets: tuple[int, ...]


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


def _item_plan(session: Session, item: TemplateItem) -> ItemPlan:
    state = users.exercise_state(session, item.exercise_id)
    step = session.get(LadderStep, state.ladder_step_id) if state is not None else None
    if step is None:  # seeding always creates state; fall back to the first rung if not
        step = min(item.exercise.ladder, key=lambda s: s.position)
    kind = ExerciseKind(item.exercise.kind)
    prescription = Prescription(
        sets=item.sets, rep_min=item.rep_min, rep_max=item.rep_max, kind=kind
    )
    history = [v for _, v in sessions_at_step(session, item.exercise_id, step.id, item.per_side)]
    return ItemPlan(
        exercise=item.exercise.name,
        kind=kind,
        step=step.name,
        cue=step.cue,
        per_side=item.per_side,
        targets=targets(prescription, history),
    )


def session_plan(session: Session, template_id: int) -> SessionPlan | None:
    """One session of the plan with today's ladder steps and targets."""
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
        items=tuple(_item_plan(session, item) for item in template.items),
        kind=template.kind,
    )


def today(session: Session, on: date, tz: ZoneInfo | None = None) -> Today | None:
    """The session at the pointer, with targets, and what has been logged on ``on``; with
    ``tz``, also the training block ``on`` falls in."""
    current = position(session)
    plan = session_plan(session, current.pointer) if current is not None else None
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
        block=blocks.current(session, on, tz) if tz is not None else None,
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
