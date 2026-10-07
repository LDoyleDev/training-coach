"""Which training block a day is in (ADR-0028), from the settings and the pause history."""

from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, Exercise, LadderStep, TemplateItem
from training_coach.domain.blocks import (
    STRENGTH_REPS,
    TOP_STEP_CUE,
    Block,
    BlockKind,
    block_on,
    history_kind,
    paused_days,
    strength_sets,
)
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.targets import Prescription
from training_coach.services import users


def current(session: Session, on: date, tz: ZoneInfo) -> Block | None:
    """The block ``on`` falls in, or None when blocks are off."""
    row = users.settings_row(session)
    if row is None or row.blocks_started_on is None:
        return None
    # A day counts unless training was paused when it began: a change made during a day takes
    # effect from the next one (a pause at 23:30 still counts that day; a resume at 09:00
    # doesn't bring back a day whose morning message was already skipped).
    changes = [
        (event.at.astimezone(tz).date() + timedelta(days=1), bool(event.payload["paused"]))
        for event in session.scalars(
            select(Event).where(Event.kind == "settings.changed").order_by(Event.at, Event.id)
        )
        if isinstance(event.payload, dict) and isinstance(event.payload.get("paused"), bool)
    ]
    return block_on(on, row.blocks_started_on, paused_days(changes, until=on))


def strength_applies(block: Block | None, session_kind: str | None) -> bool:
    """Whether a session gets the strength prescription: strength sessions in strength blocks."""
    return block is not None and block.kind is BlockKind.STRENGTH and session_kind == "strength"


def _current_step(session: Session, exercise: Exercise) -> LadderStep:
    state = users.exercise_state(session, exercise.id)
    step = session.get(LadderStep, state.ladder_step_id) if state is not None else None
    # Seeding always creates state; fall back to the first rung if not.
    return step if step is not None else min(exercise.ladder, key=lambda s: s.position)


def step_for(session: Session, exercise: Exercise, strength: bool) -> tuple[LadderStep, bool]:
    """The step trained and whether it's the top of the ladder with the tempo cue added: one
    step harder for rep-counted work under the strength prescription, else the current step."""
    current = _current_step(session, exercise)
    if not strength or ExerciseKind(exercise.kind) is not ExerciseKind.REPS:
        return current, False
    harder = session.scalar(
        select(LadderStep)
        .where(LadderStep.exercise_id == exercise.id, LadderStep.position > current.position)
        .order_by(LadderStep.position)
        .limit(1)
    )
    return (harder, False) if harder is not None else (current, True)


@dataclass(frozen=True)
class Assignment:
    """What one planned exercise asks for today (ADR-0028)."""

    step: LadderStep
    cue: str | None
    prescription: Prescription
    history: BlockKind | None  # which block's sessions its targets come from


def assign(session: Session, item: TemplateItem, strength: bool) -> Assignment:
    kind = ExerciseKind(item.exercise.kind)
    step, at_top = step_for(session, item.exercise, strength)
    if not strength or kind is not ExerciseKind.REPS:
        return Assignment(
            step=step,
            cue=step.cue,
            prescription=Prescription(item.sets, item.rep_min, item.rep_max, kind),
            history=history_kind(kind, BlockKind.HYPERTROPHY),
        )
    low, high = STRENGTH_REPS
    cue = step.cue
    if at_top:
        cue = f"{cue}. {TOP_STEP_CUE}" if cue else TOP_STEP_CUE
    return Assignment(
        step=step,
        cue=cue,
        prescription=Prescription(strength_sets(item.sets), low, high, kind),
        history=BlockKind.STRENGTH,
    )
