"""Turning typed logs into saved workouts (step 1-E; ADR-0006, ADR-0014, ADR-0016, ADR-0022).

The bot parses a message into a ``Draft``, shows it, and calls ``save`` only after "Save".
Every draft carries a random token stored on the workout, so saving the same draft twice
(a double tap, a duplicate Telegram callback) returns the first workout and changes nothing.
The caller owns the transaction.
"""

import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    PlanState,
    SessionTemplate,
    SetLog,
    TemplateItem,
    Workout,
)
from training_coach.domain.enums import ExerciseKind, WorkoutStatus
from training_coach.domain.parser import Entry, Known, ParseResult, parse_log
from training_coach.domain.queue import ADVANCING, complete
from training_coach.services.today import position


@dataclass(frozen=True)
class Draft:
    """What the user is asked to confirm. ``template_id`` None means an extra session."""

    token: str
    template_id: int | None
    session_name: str  # "Upper" or "Extra session"
    entries: tuple[Entry, ...]
    problems: tuple[str, ...]


@dataclass(frozen=True)
class Saved:
    workout_id: int
    already_saved: bool  # True when this draft had been saved before: nothing changed


def _day_start_utc(on: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(on, time(0), tzinfo=tz).astimezone(UTC)


def target(session: Session, on: date, tz: ZoneInfo) -> SessionTemplate | None:
    """The planned session a log on ``on`` belongs to, or None for an extra (ADR-0014).

    Once a planned session is done or rested today, further logs are extras. Otherwise it is
    the session picked today with "Pick another" (ADR-0022), else the one at the pointer.
    """
    done_today = session.scalar(
        select(Workout.id).where(
            Workout.local_date == on,
            Workout.template_id.is_not(None),
            Workout.status.in_(ADVANCING),
        )
    )
    if done_today is not None:
        return None
    picked = session.scalar(
        select(Event.payload)
        .where(Event.kind == "queue.picked", Event.at >= _day_start_utc(on, tz))
        .order_by(Event.id.desc())
        .limit(1)
    )
    if picked is not None:
        template = session.get(SessionTemplate, picked.get("picked"))
        if template is not None:
            return template
    current = position(session)
    return session.get(SessionTemplate, current.pointer) if current is not None else None


def catalogue(session: Session, template: SessionTemplate | None) -> list[Known]:
    """Every exercise a log may name. Whether it is one-sided comes from the target session's
    item when there is one, else from any session that uses it."""
    rows = list(
        session.execute(
            select(TemplateItem.exercise_id, TemplateItem.per_side, TemplateItem.template_id)
        )
    )
    in_target = {e: flag for e, flag, t in rows if template is not None and t == template.id}
    anywhere: dict[int, bool] = {}
    for e, flag, _ in rows:
        anywhere[e] = anywhere.get(e, False) or flag

    def one_sided(exercise_id: int) -> bool:
        return in_target.get(exercise_id, anywhere.get(exercise_id, False))

    return [
        Known(e.slug, (e.name, *e.aliases), ExerciseKind(e.kind), one_sided(e.id))
        for e in session.scalars(select(Exercise).order_by(Exercise.id))
    ]


def draft(session: Session, text: str, on: date, tz: ZoneInfo) -> Draft:
    """Parse a message into something to confirm. Never writes."""
    template = target(session, on, tz)
    parsed: ParseResult = parse_log(text, catalogue(session, template))
    return Draft(
        token=secrets.token_hex(16),
        template_id=template.id if template is not None else None,
        session_name=template.name if template is not None else "Extra session",
        entries=parsed.entries,
        problems=parsed.problems,
    )


def save(session: Session, confirmed: Draft, on: date) -> Saved | None:
    """Write the workout, its sets at the current ladder steps and the queue move.

    Returns None when there is nothing to save (no entries). A draft saved before returns
    that workout with ``already_saved`` and writes nothing.
    """
    existing = session.scalar(select(Workout.id).where(Workout.log_token == confirmed.token))
    if existing is not None:
        return Saved(existing, already_saved=True)
    if not confirmed.entries:
        return None

    exercises = {
        e.slug: e
        for e in session.scalars(
            select(Exercise).where(Exercise.slug.in_([x.slug for x in confirmed.entries]))
        )
    }
    workout = Workout(
        local_date=on,
        template_id=confirmed.template_id,
        status=WorkoutStatus.DONE,  # only done workouts carry sets (rest/skip have none)
        log_token=confirmed.token,
    )
    for entry in confirmed.entries:
        exercise = exercises[entry.slug]
        state = session.get(ExerciseState, exercise.id)
        step_id = (
            state.ladder_step_id
            if state is not None
            else min(exercise.ladder, key=lambda s: s.position).id
        )
        workout.sets.extend(
            SetLog(exercise_id=exercise.id, ladder_step_id=step_id, set_no=n, side=side, value=v)
            for n, side, v in entry.sets
        )
    session.add(workout)

    plan = session.get(PlanState, 1)
    current = position(session)
    if plan is not None and current is not None:
        order = list(session.scalars(select(SessionTemplate.id).order_by(SessionTemplate.position)))
        moved = complete(order, current, confirmed.template_id, WorkoutStatus.DONE)
        if moved != current:
            plan.next_template_id = moved.pointer
            plan.queued = list(moved.queued)
    session.flush()
    session.add(
        Event(
            kind="workout.logged",
            payload={
                "workout_id": workout.id,
                "template_id": confirmed.template_id,
                "exercises": len(confirmed.entries),
                "sets": len(workout.sets),
            },
        )
    )
    return Saved(workout.id, already_saved=False)
