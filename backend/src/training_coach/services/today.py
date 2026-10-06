"""Today's session and the week ahead, read from the database (ADR-0006, ADR-0014, ADR-0016).

Returns plain data; the bot formats it. ``None`` means there is no plan in the database (for
example a failed seed on a fresh install, ADR-0015), which callers must tell the user about.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import (
    ExerciseState,
    LadderStep,
    PlanState,
    SessionTemplate,
    SetLog,
    TemplateItem,
    Workout,
)
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus
from training_coach.domain.progression import combine_sides
from training_coach.domain.queue import ADVANCING, upcoming
from training_coach.domain.targets import Prescription, targets


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
    name: str
    focus: str
    optional: bool
    items: tuple[ItemPlan, ...]


@dataclass(frozen=True)
class Today:
    session: SessionPlan
    logged_today: tuple[str, ...]  # "Legs (done)", one per workout already logged today


@dataclass(frozen=True)
class Day:
    date: date
    session: str


def _order(session: Session) -> list[SessionTemplate]:
    query = select(SessionTemplate).order_by(SessionTemplate.position)
    return list(session.scalars(query))


def _pointer(session: Session) -> int | None:
    state = session.get(PlanState, 1)
    return state.next_template_id if state is not None else None


def _last_values(session: Session, item: TemplateItem, step_id: int) -> list[int] | None:
    """Per-set values from the most recent done workout with this exercise at this step."""
    workout_id = session.scalar(
        select(Workout.id)
        .join(SetLog)
        .where(
            Workout.status == WorkoutStatus.DONE,
            SetLog.exercise_id == item.exercise_id,
            SetLog.ladder_step_id == step_id,
        )
        .order_by(Workout.local_date.desc(), Workout.created_at.desc())
        .limit(1)
    )
    if workout_id is None:
        return None
    rows = session.execute(
        select(SetLog.set_no, SetLog.side, SetLog.value).where(
            SetLog.workout_id == workout_id, SetLog.exercise_id == item.exercise_id
        )
    )
    return combine_sides(((n, Side(s), v) for n, s, v in rows), unilateral=item.per_side)


def _item_plan(session: Session, item: TemplateItem) -> ItemPlan:
    state = session.get(ExerciseState, item.exercise_id)
    step = session.get(LadderStep, state.ladder_step_id) if state is not None else None
    if step is None:  # seeding always creates state; fall back to the first rung if not
        step = min(item.exercise.ladder, key=lambda s: s.position)
    prescription = Prescription(sets=item.sets, rep_min=item.rep_min, rep_max=item.rep_max)
    return ItemPlan(
        exercise=item.exercise.name,
        kind=ExerciseKind(item.exercise.kind),
        step=step.name,
        cue=step.cue,
        per_side=item.per_side,
        targets=targets(prescription, _last_values(session, item, step.id)),
    )


def today(session: Session, on: date) -> Today | None:
    """The session at the pointer, with targets, and what has been logged on ``on``."""
    pointer = _pointer(session)
    template = (
        session.scalar(
            select(SessionTemplate)
            .where(SessionTemplate.id == pointer)
            .options(selectinload(SessionTemplate.items).selectinload(TemplateItem.exercise))
        )
        if pointer is not None
        else None
    )
    if template is None:
        return None
    names = {t.id: t.name for t in _order(session)}
    logged = session.scalars(
        select(Workout).where(Workout.local_date == on).order_by(Workout.created_at)
    )
    return Today(
        session=SessionPlan(
            name=template.name,
            focus=template.focus,
            optional=template.is_rest_optional,
            items=tuple(_item_plan(session, item) for item in template.items),
        ),
        logged_today=tuple(
            f"{names[w.template_id] if w.template_id else 'Extra'} ({w.status})" for w in logged
        ),
    )


def week(session: Session, on: date, days: int = 7) -> list[Day] | None:
    """The next ``days`` sessions, dated as if each is done on its day (ADR-0006).

    Starts tomorrow when today's planned session is already done or rested.
    """
    pointer = _pointer(session)
    order = _order(session)
    ids = [t.id for t in order]
    if pointer is None or pointer not in ids:
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
        for i, template_id in enumerate(upcoming(ids, pointer, days))
    ]
