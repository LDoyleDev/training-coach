"""Feedback after a save, and moving up the ladder (step 1-G; ADR-0016, ADR-0025).

``feedback`` reports new personal bests and the progression status of each exercise in a saved
workout. ``move_up`` and ``not_yet`` answer the "ready to progress" prompt; ``move_up`` checks
everything again when pressed, so a stale or forged press changes nothing. The caller owns the
transaction.
"""

from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    LadderStep,
    SessionTemplate,
    SetLog,
    TemplateItem,
    Workout,
)
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus
from training_coach.domain.progression import Progress, assess, combine_sides
from training_coach.domain.records import NewBests, new_bests
from training_coach.domain.targets import Prescription

TOP_NOTED = "progress.top_of_ladder"


@dataclass(frozen=True)
class Feedback:
    """What one exercise in a saved workout earned."""

    exercise_id: int
    exercise: str
    kind: ExerciseKind
    step_id: int
    bests: NewBests
    status: Progress
    next_step: str | None  # the harder variation, when ready
    note_top: bool  # the rule is met on the last step and hasn't been mentioned before


class MoveOutcome(StrEnum):
    MOVED = "moved"
    ALREADY_MOVED = "already_moved"  # the step changed since the prompt: nothing to do
    NOT_READY = "not_ready"
    NO_NEXT_STEP = "no_next_step"


@dataclass(frozen=True)
class Move:
    outcome: MoveOutcome
    exercise: str
    step: str | None = None  # the step trained from now on, when moved


def _items(session: Session, exercise_id: int) -> list[TemplateItem]:
    """The plan's prescriptions for an exercise, in plan order."""
    return list(
        session.scalars(
            select(TemplateItem)
            .join(SessionTemplate)
            .where(TemplateItem.exercise_id == exercise_id)
            .order_by(SessionTemplate.position, TemplateItem.position)
        )
    )


def _item(session: Session, exercise_id: int, template_id: int | None) -> TemplateItem | None:
    """The prescription a log is judged against: the logged session's, else the plan's first
    (an extra session, or an exercise the logged session doesn't list)."""
    items = _items(session, exercise_id)
    in_session = [i for i in items if i.template_id == template_id]
    candidates = in_session or items
    return candidates[0] if candidates else None


def _prescription(item: TemplateItem) -> Prescription:
    return Prescription(sets=item.sets, rep_min=item.rep_min, rep_max=item.rep_max)


def _sessions(
    session: Session, exercise_id: int, step_id: int, per_side: bool
) -> list[tuple[int, list[int]]]:
    """Every done workout's per-set values for this exercise at this step, newest first."""
    rows = session.execute(
        select(SetLog.workout_id, SetLog.set_no, SetLog.side, SetLog.value)
        .join(Workout)
        .where(
            Workout.status == WorkoutStatus.DONE,
            SetLog.exercise_id == exercise_id,
            SetLog.ladder_step_id == step_id,
        )
        .order_by(Workout.local_date.desc(), Workout.created_at.desc(), Workout.id.desc())
    )
    grouped: dict[int, list[tuple[int, Side, int]]] = {}
    for workout_id, set_no, side, value in rows:
        grouped.setdefault(workout_id, []).append((set_no, Side(side), value))
    return [(w, combine_sides(sets, unilateral=per_side)) for w, sets in grouped.items()]


def _next_step(session: Session, step: LadderStep) -> LadderStep | None:
    return session.scalar(
        select(LadderStep)
        .where(LadderStep.exercise_id == step.exercise_id, LadderStep.position > step.position)
        .order_by(LadderStep.position)
        .limit(1)
    )


def _status(session: Session, item: TemplateItem | None, step: LadderStep) -> Progress:
    if item is None:
        return Progress.HOLD
    recent = [v for _, v in _sessions(session, step.exercise_id, step.id, item.per_side)]
    return assess(_prescription(item), recent, has_next_step=_next_step(session, step) is not None)


def _top_noted(session: Session, exercise_id: int, step_id: int) -> bool:
    payloads = session.scalars(select(Event.payload).where(Event.kind == TOP_NOTED))
    return any(
        isinstance(p, dict) and p.get("exercise_id") == exercise_id and p.get("step_id") == step_id
        for p in payloads
    )


def feedback(session: Session, workout_id: int) -> list[Feedback]:
    """Bests and progression for each exercise in a just-saved workout, in logged order.

    Records the top-of-ladder note as given, so it is said once per exercise and step."""
    workout = session.get(Workout, workout_id)
    if workout is None:
        return []
    logged: dict[tuple[int, int], None] = {}
    for row in sorted(workout.sets, key=lambda s: s.id):
        logged.setdefault((row.exercise_id, row.ladder_step_id), None)

    result = []
    for exercise_id, step_id in logged:
        exercise = session.get(Exercise, exercise_id)
        step = session.get(LadderStep, step_id)
        if exercise is None or step is None:
            continue
        item = _item(session, exercise_id, workout.template_id)
        per_side = item.per_side if item is not None else False
        history = _sessions(session, exercise_id, step_id, per_side)
        # History is newest first, so what follows this workout came before it: a backdated
        # log is compared with the sessions before its day, not with later ones.
        at = next((i for i, (w, _) in enumerate(history) if w == workout_id), len(history))
        current = history[at][1] if at < len(history) else []
        bests = new_bests(current, (v for _, v in history[at + 1 :]))
        state = session.get(ExerciseState, exercise_id)
        # Progression is about the step being trained now; a log at an older step only
        # counts for bests.
        on_current = state is not None and state.ladder_step_id == step_id
        status = _status(session, item, step) if on_current else Progress.HOLD
        upcoming = _next_step(session, step) if status is Progress.READY else None
        note_top = status is Progress.TOP_OF_LADDER and not _top_noted(
            session, exercise_id, step_id
        )
        if note_top:
            session.add(
                Event(kind=TOP_NOTED, payload={"exercise_id": exercise_id, "step_id": step_id})
            )
        result.append(
            Feedback(
                exercise_id=exercise_id,
                exercise=exercise.name,
                kind=ExerciseKind(exercise.kind),
                step_id=step_id,
                bests=bests,
                status=status,
                next_step=upcoming.name if upcoming is not None else None,
                note_top=note_top,
            )
        )
    return result


def move_up(session: Session, exercise_id: int, from_step_id: int) -> Move | None:
    """Move to the next ladder step if the exercise is still on ``from_step_id`` and still
    ready under one of its prescriptions. None for an exercise that doesn't exist."""
    exercise = session.get(Exercise, exercise_id)
    state = session.get(ExerciseState, exercise_id)
    if exercise is None or state is None:
        return None
    if state.ladder_step_id != from_step_id:
        return Move(MoveOutcome.ALREADY_MOVED, exercise.name)
    step = session.get(LadderStep, from_step_id)
    if step is None:  # the composite foreign key keeps it; this narrows the type
        return None
    upcoming = _next_step(session, step)
    if upcoming is None:
        return Move(MoveOutcome.NO_NEXT_STEP, exercise.name)
    if not any(
        _status(session, item, step) is Progress.READY for item in _items(session, exercise_id)
    ):
        return Move(MoveOutcome.NOT_READY, exercise.name)
    state.ladder_step_id = upcoming.id
    session.add(
        Event(
            kind="progress.moved_up",
            payload={
                "exercise_id": exercise_id,
                "from_step_id": step.id,
                "to_step_id": upcoming.id,
            },
        )
    )
    return Move(MoveOutcome.MOVED, exercise.name, upcoming.name)


def not_yet(session: Session, exercise_id: int, step_id: int) -> str | None:
    """Record the choice to stay. The prompt comes back after the next session that still
    meets the rule. Returns the exercise and step names, or None if they don't exist."""
    exercise = session.get(Exercise, exercise_id)
    step = session.get(LadderStep, step_id)
    if exercise is None or step is None or step.exercise_id != exercise_id:
        return None
    session.add(
        Event(kind="progress.not_yet", payload={"exercise_id": exercise_id, "step_id": step_id})
    )
    return f"{exercise.name} ({step.name})"
