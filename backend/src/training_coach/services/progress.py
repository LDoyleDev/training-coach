"""Feedback after a save, and moving up the ladder (step 1-G; ADR-0016, ADR-0025).

``feedback`` reports new personal bests and the progression status of each exercise in a saved
workout. ``move_up`` and ``not_yet`` answer the "ready to progress" prompt; ``move_up`` checks
everything again when pressed, so a stale or forged press changes nothing. The caller owns the
transaction.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    LadderStep,
    SessionTemplate,
    SetLog,
    TemplateItem,
    Workout,
)
from training_coach.domain.blocks import BlockKind, history_kind
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus
from training_coach.domain.progression import Progress, assess, combine_sides
from training_coach.domain.queue import local_date
from training_coach.domain.records import NewBests, new_bests
from training_coach.domain.targets import Prescription
from training_coach.services import blocks, users

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
    STRENGTH_BLOCK = "strength_block"  # moving up waits for the hypertrophy block (ADR-0028)


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
    return Prescription(
        sets=item.sets,
        rep_min=item.rep_min,
        rep_max=item.rep_max,
        kind=ExerciseKind(item.exercise.kind),
    )


def sessions_at_step(
    session: Session,
    exercise_id: int,
    step_id: int,
    per_side: bool,
    block: BlockKind | None = None,
) -> list[tuple[int, list[int]]]:
    """Every done workout's per-set values for this exercise at this step, newest first.

    ``block`` keeps strength and hypertrophy history apart (ADR-0028): ``STRENGTH`` only
    strength-block workouts, ``HYPERTROPHY`` everything else, None both."""
    query = (
        select(SetLog.workout_id, SetLog.set_no, SetLog.side, SetLog.value)
        .join(Workout)
        .where(
            Workout.status == WorkoutStatus.DONE,
            SetLog.exercise_id == exercise_id,
            SetLog.ladder_step_id == step_id,
        )
        .order_by(Workout.local_date.desc(), Workout.created_at.desc(), Workout.id.desc())
    )
    if block is BlockKind.STRENGTH:
        query = query.where(Workout.block == BlockKind.STRENGTH)
    elif block is BlockKind.HYPERTROPHY:
        query = query.where(or_(Workout.block.is_(None), Workout.block != BlockKind.STRENGTH))
    rows = session.execute(query)
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
    # Readiness is judged on the hypertrophy prescription and its history (ADR-0028).
    block = history_kind(ExerciseKind(item.exercise.kind), BlockKind.HYPERTROPHY)
    recent = [
        v for _, v in sessions_at_step(session, step.exercise_id, step.id, item.per_side, block)
    ]
    return assess(_prescription(item), recent, has_next_step=_next_step(session, step) is not None)


def _top_noted(session: Session, exercise_id: int, step_id: int) -> bool:
    payloads = session.scalars(select(Event.payload).where(Event.kind == TOP_NOTED))
    return any(
        isinstance(p, dict) and p.get("exercise_id") == exercise_id and p.get("step_id") == step_id
        for p in payloads
    )


def bests_in(
    session: Session,
    workout_id: int,
    exercise_id: int,
    step_id: int,
    per_side: bool,
    block: BlockKind | None = None,
) -> NewBests:
    """The records one workout set for an exercise at a step, against the sessions before it
    (of the same block kind, when ``block`` is given)."""
    history = sessions_at_step(session, exercise_id, step_id, per_side, block)
    # History is newest first, so what follows this workout came before it: a backdated log
    # is compared with the sessions before its day, not with later ones.
    at = next((i for i, (w, _) in enumerate(history) if w == workout_id), len(history))
    current = history[at][1] if at < len(history) else []
    return new_bests(current, (v for _, v in history[at + 1 :]))


def workout_history(workout: Workout, exercise: Exercise) -> BlockKind | None:
    """The block history a workout's sets of ``exercise`` belong to."""
    prescribed = (
        BlockKind.STRENGTH if workout.block == BlockKind.STRENGTH else BlockKind.HYPERTROPHY
    )
    return history_kind(ExerciseKind(exercise.kind), prescribed)


def per_side_for(session: Session, exercise_id: int, template_id: int | None) -> bool:
    """One side at a time: as the session's item says, else as the exercise does (#107)."""
    item = _item(session, exercise_id, template_id)
    if item is not None:
        return item.per_side
    exercise = session.get(Exercise, exercise_id)
    return exercise.per_side if exercise is not None else False


def feedback(session: Session, workout_id: int, tz: ZoneInfo | None = None) -> list[Feedback]:
    """Bests and progression for each exercise in a just-saved workout, in logged order.

    Records the top-of-ladder note as given, so it is said once per exercise and step. With
    ``tz``, no Move up is offered while a strength block is on (ADR-0028)."""
    workout = session.get(Workout, workout_id)
    if workout is None:
        return []
    # Held if the workout's day or today is in a strength block: a log drafted before midnight
    # and saved on the first strength day mustn't offer a move the bot would then refuse.
    days = (workout.local_date, local_date(datetime.now(UTC), tz)) if tz is not None else ()
    in_strength = workout.block == BlockKind.STRENGTH or any(
        (block := blocks.current(session, day, tz)) is not None and block.kind is BlockKind.STRENGTH
        for day in days
        if tz is not None
    )
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
        # A retired exercise has no item, so it is never ready (#107); bests still count.
        per_side = item.per_side if item is not None else exercise.per_side
        bests = bests_in(
            session, workout_id, exercise_id, step_id, per_side, workout_history(workout, exercise)
        )
        state = users.exercise_state(session, exercise_id)
        # Progression is about the step being trained now, outside strength blocks; a log at
        # an older step, or a strength-block session, only counts for bests (ADR-0028).
        on_current = state is not None and state.ladder_step_id == step_id and not in_strength
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


def move_up(
    session: Session, exercise_id: int, from_step_id: int, *, strength_block: bool = False
) -> Move | None:
    """Move to the next ladder step if the exercise is still on ``from_step_id`` and still
    ready under one of its prescriptions, and it isn't a strength block (ADR-0028). None for
    an exercise that doesn't exist."""
    exercise = session.get(Exercise, exercise_id)
    state = users.exercise_state(session, exercise_id)
    if exercise is None or state is None:
        return None
    if strength_block:
        return Move(MoveOutcome.STRENGTH_BLOCK, exercise.name)
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


@dataclass(frozen=True)
class Standing:
    """One exercise in /progress."""

    exercise_id: int
    exercise: str
    kind: ExerciseKind
    step_id: int
    step: str
    step_number: int  # 1-based position on the ladder
    steps: int
    last: tuple[int, ...]  # the latest session at this step; empty if none yet
    best_set: int | None
    status: Progress
    retired: bool = False  # out of the plan (#107): shown for its history, never ready
    # The best set of each session at this step, newest first (up to RECENT), for a trend.
    recent: tuple[int, ...] = ()


RECENT = 12


def overview(session: Session) -> list[Standing]:
    """Every exercise in plan order (first session it appears in), then any the plan doesn't
    use. Ready means ready under at least one of its prescriptions, as Move up checks."""
    order: dict[int, None] = {}
    for item in session.scalars(
        select(TemplateItem)
        .join(SessionTemplate)
        .order_by(SessionTemplate.position, TemplateItem.position)
    ):
        order.setdefault(item.exercise_id, None)
    for exercise_id in session.scalars(select(Exercise.id).order_by(Exercise.id)):
        order.setdefault(exercise_id, None)

    result = []
    for exercise_id in order:
        exercise = session.get(Exercise, exercise_id)
        state = users.exercise_state(session, exercise_id)
        step = session.get(LadderStep, state.ladder_step_id) if state is not None else None
        if exercise is None or step is None:
            continue
        items = _items(session, exercise_id)
        # Display only: "last" and "best" use the first prescription's sides. Readiness is
        # judged per prescription below, exactly as Move up re-checks it.
        per_side = items[0].per_side if items else exercise.per_side
        block = history_kind(ExerciseKind(exercise.kind), BlockKind.HYPERTROPHY)
        history = [v for _, v in sessions_at_step(session, exercise_id, step.id, per_side, block)]
        if exercise.retired and not history:
            continue  # nothing to show for an exercise no longer trained (#107)
        statuses = {_status(session, item, step) for item in items}
        status = next(
            (s for s in (Progress.READY, Progress.TOP_OF_LADDER) if s in statuses), Progress.HOLD
        )
        result.append(
            Standing(
                exercise_id=exercise_id,
                exercise=exercise.name,
                kind=ExerciseKind(exercise.kind),
                step_id=step.id,
                step=step.name,
                step_number=step.position + 1,
                steps=len(exercise.ladder),
                last=tuple(history[0]) if history else (),
                best_set=max((max(v, default=0) for v in history), default=None),
                status=status,
                retired=exercise.retired,
                recent=tuple(max(v, default=0) for v in history[:RECENT]),
            )
        )
    return result
