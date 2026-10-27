"""Feedback after a save, and moving up the ladder (step 1-G; ADR-0016, ADR-0025, ADR-0075).

``feedback`` reports new personal bests and the progression status of each exercise in a saved
workout. ``move_up`` and ``not_yet`` answer the "ready to progress" prompt; ``move_up`` checks
everything again when pressed, so a stale or forged press changes nothing. ``set_level`` puts an
exercise on any step of its own ladder by hand, ready or not (ADR-0075). The caller owns the
transaction.

Steps lock by kit (ADR-0071): once a person has listed their kit, Move up goes to the next step
it allows; past the last one the exercise is at the top for their kit, and ``unlock`` names what
opens the next step. A locked level can still be chosen by hand, with a warning.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy import Select, or_, select
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
from training_coach.domain import kit as kit_rules
from training_coach.domain.blocks import BlockKind, history_kind
from training_coach.domain.enums import ExerciseKind, Place, Places, Side, WorkoutStatus
from training_coach.domain.kit import Item
from training_coach.domain.load import top_weight
from training_coach.domain.progression import Progress, assess, combine_sides
from training_coach.domain.queue import local_date
from training_coach.domain.records import NewBests, new_bests
from training_coach.domain.targets import Prescription
from training_coach.services import blocks, equipment, user_settings, users

TOP_NOTED = "progress.top_of_ladder"
LEVEL_SET = "progress.level_set"


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
    slug: str = ""  # the exercise's, for a link to its ladder (ADR-0075)
    unlock: str | None = None  # at the top for the kit: what opens the next step (ADR-0071)


class MoveOutcome(StrEnum):
    MOVED = "moved"
    ALREADY_MOVED = "already_moved"  # the step changed since the prompt: nothing to do
    NOT_READY = "not_ready"
    NO_NEXT_STEP = "no_next_step"
    STRENGTH_BLOCK = "strength_block"  # moving up waits for the hypertrophy block (ADR-0028)
    STAYED = "stayed"  # Not yet, recorded
    LEVEL_SET = "level_set"  # put on a step by hand (ADR-0075)
    SAME_LEVEL = "same_level"  # already on that step: nothing to do


@dataclass(frozen=True)
class Move:
    outcome: MoveOutcome
    exercise: str
    step: str | None = None  # the step trained from now on, when moved
    warning: str | None = None  # a level chosen by hand that the kit doesn't allow (ADR-0071)


def _items(session: Session, exercise_id: int) -> list[TemplateItem]:
    """The plan's prescriptions for an exercise, in plan order."""
    return list(
        session.scalars(
            select(TemplateItem)
            .join(SessionTemplate)
            .where(TemplateItem.exercise_id == exercise_id)
            # A session's home version first, then its gym version (ADR-0071).
            .order_by(
                SessionTemplate.position, TemplateItem.place != Place.HOME, TemplateItem.position
            )
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
    weight: float | None = None,
) -> list[tuple[int, list[int]]]:
    """Every done workout's per-set values for this exercise at this step, newest first.

    ``block`` keeps strength and hypertrophy history apart (ADR-0028): ``STRENGTH`` only
    strength-block workouts, ``HYPERTROPHY`` everything else, None both. ``weight`` keeps only
    the workouts whose heaviest set used it, on a loaded step (ADR-0072)."""
    query = (
        select(SetLog.workout_id, SetLog.set_no, SetLog.side, SetLog.value, SetLog.load_kg)
        .join(Workout)
        .where(
            Workout.status == WorkoutStatus.DONE,
            SetLog.exercise_id == exercise_id,
            SetLog.ladder_step_id == step_id,
        )
        .order_by(Workout.local_date.desc(), Workout.created_at.desc(), Workout.id.desc())
    )
    rows = session.execute(_in_block(query, block))
    grouped: dict[int, list[tuple[int, Side, int]]] = {}
    heaviest: dict[int, float | None] = {}
    for workout_id, set_no, side, value, kg in rows:
        grouped.setdefault(workout_id, []).append((set_no, Side(side), value))
        if kg is not None:
            heaviest[workout_id] = max(kg, heaviest.get(workout_id) or kg)
    return [
        (w, combine_sides(sets, unilateral=per_side))
        for w, sets in grouped.items()
        if weight is None or heaviest.get(w) == weight
    ]


def _in_block[*Ts](query: Select[*Ts], block: BlockKind | None) -> Select[*Ts]:
    """``query`` kept to one block's workouts (ADR-0028): ``STRENGTH`` only strength-block
    workouts, ``HYPERTROPHY`` everything else, None both."""
    if block is BlockKind.STRENGTH:
        return query.where(Workout.block == BlockKind.STRENGTH)
    if block is BlockKind.HYPERTROPHY:
        return query.where(or_(Workout.block.is_(None), Workout.block != BlockKind.STRENGTH))
    return query


def last_loads(
    session: Session, exercise_id: int, step_id: int, block: BlockKind | None = None
) -> list[tuple[int, float]]:
    """The (set number, kg) of the last done workout with a weight for this exercise at this
    step, in ``block`` as ``sessions_at_step`` reads it: where the set screen starts (ADR-0072).
    Empty with no weight logged there yet."""
    query = (
        select(SetLog.workout_id, SetLog.set_no, SetLog.load_kg)
        .join(Workout)
        .where(
            Workout.status == WorkoutStatus.DONE,
            SetLog.exercise_id == exercise_id,
            SetLog.ladder_step_id == step_id,
            SetLog.load_kg.is_not(None),
        )
        .order_by(
            Workout.local_date.desc(), Workout.created_at.desc(), Workout.id.desc(), SetLog.set_no
        )
    )
    rows = list(session.execute(_in_block(query, block)))
    last = rows[0].workout_id if rows else None
    return [(n, kg) for w, n, kg in rows if w == last and kg is not None]


Kit = Sequence[Item] | None  # None: no kit listed yet, so nothing locks


def _at(step: LadderStep) -> tuple[list[LadderStep], int]:
    ladder = step.exercise.ladder
    return ladder, next(i for i, s in enumerate(ladder) if s.id == step.id)


def _next_step(step: LadderStep, kit: Kit) -> LadderStep | None:
    """The next step the kit allows: Move up skips the locked ones (ADR-0071)."""
    ladder, at = _at(step)
    found = kit_rules.next_open(equipment.ladder_needs(step.exercise), at, kit)
    return ladder[found] if found is not None else None


def _unlock(step: LadderStep, kit: Kit) -> str | None:
    """At the top for the kit: "a 16 kg kettlebell unlocks One-arm, 16 kg"; else None."""
    ladder, at = _at(step)
    lacking = kit_rules.unlocks_next(equipment.ladder_needs(step.exercise), at, kit)
    return f"{' and '.join(lacking)} unlocks {ladder[at + 1].name}" if lacking else None


def _status(
    session: Session, item: TemplateItem | None, step: LadderStep, kit: Kit = None
) -> Progress:
    if item is None or blocks.load_kit(step.exercise.slug, step.name) is not None:
        # A loaded step gets harder by weight, suggested on the set screen (ADR-0072).
        return Progress.HOLD
    # Readiness is judged on the hypertrophy prescription and its history (ADR-0028).
    block = history_kind(ExerciseKind(item.exercise.kind), BlockKind.HYPERTROPHY)
    recent = [
        v for _, v in sessions_at_step(session, step.exercise_id, step.id, item.per_side, block)
    ]
    upcoming = _next_step(step, kit)
    return assess(_prescription(item), recent, has_next_step=upcoming is not None)


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
    weight: float | None = None,
) -> NewBests:
    """The records one workout set for an exercise at a step, against the sessions before it
    (of the same block kind, when ``block`` is given; at the same ``weight``, on a loaded
    step: more reps at a lighter weight is no record, ADR-0072)."""
    history = sessions_at_step(session, exercise_id, step_id, per_side, block, weight)
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

    kit = equipment.kit(session)
    result = []
    for exercise_id, step_id in logged:
        exercise = session.get(Exercise, exercise_id)
        step = session.get(LadderStep, step_id)
        if exercise is None or step is None:
            continue
        item = _item(session, exercise_id, workout.template_id)
        # A retired exercise has no item, so it is never ready (#107); bests still count.
        per_side = item.per_side if item is not None else exercise.per_side
        weight = top_weight(
            [
                (s.set_no, s.load_kg)
                for s in workout.sets
                if s.exercise_id == exercise_id and s.load_kg is not None
            ]
        )
        history = workout_history(workout, exercise)
        bests = bests_in(session, workout_id, exercise_id, step_id, per_side, history, weight)
        state = users.exercise_state(session, exercise_id)
        # Progression is about the step being trained now, outside strength blocks; a log at
        # an older step, or a strength-block session, only counts for bests (ADR-0028).
        on_current = state is not None and state.ladder_step_id == step_id and not in_strength
        status = _status(session, item, step, kit) if on_current else Progress.HOLD
        upcoming = _next_step(step, kit) if status is Progress.READY else None
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
                slug=exercise.slug,
                unlock=_unlock(step, kit) if status is Progress.TOP_OF_LADDER else None,
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
    kit = equipment.kit(session)
    upcoming = _next_step(step, kit)
    if upcoming is None:  # the last step, or the last the kit allows
        return Move(MoveOutcome.NO_NEXT_STEP, exercise.name)
    if not any(
        _status(session, item, step, kit) is Progress.READY for item in _items(session, exercise_id)
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


def exercise_id_for(session: Session, slug: str) -> int | None:
    """The exercise with this slug, or None."""
    return session.scalar(select(Exercise.id).where(Exercise.slug == slug))


def in_strength_block(session: Session, on: date, tz: ZoneInfo) -> bool:
    """Whether ``on`` falls in a strength block, when moving up waits (ADR-0028)."""
    block = blocks.current(session, on, tz)
    return block is not None and block.kind is BlockKind.STRENGTH


def stay(session: Session, exercise_id: int, step_id: int) -> Move | None:
    """Not yet, from the web: recorded only while the exercise is still on ``step_id``, so a
    stale page changes nothing. None for an exercise or step that doesn't exist."""
    exercise = session.get(Exercise, exercise_id)
    state = users.exercise_state(session, exercise_id)
    step = session.get(LadderStep, step_id)
    if exercise is None or state is None or step is None or step.exercise_id != exercise_id:
        return None
    if state.ladder_step_id != step_id:
        return Move(MoveOutcome.ALREADY_MOVED, exercise.name)
    not_yet(session, exercise_id, step_id)
    return Move(MoveOutcome.STAYED, exercise.name, step.name)


def set_level(session: Session, exercise_id: int, step_id: int) -> Move | None:
    """Put the exercise on ``step_id``, up or down, by hand (ADR-0075). Never needs "ready" and
    is allowed in a strength block: it is the person's choice, not the rule's. Targets then come
    from that step's own history. None for an exercise that doesn't exist or a step that isn't on
    its ladder."""
    exercise = session.get(Exercise, exercise_id)
    state = users.exercise_state(session, exercise_id)
    step = session.get(LadderStep, step_id)
    if exercise is None or state is None or step is None or step.exercise_id != exercise_id:
        return None
    if state.ladder_step_id == step_id:
        return Move(MoveOutcome.SAME_LEVEL, exercise.name, step.name)
    # A step the kit doesn't allow is still the person's to choose: say so, don't refuse.
    lacking = kit_rules.missing(
        equipment.kit(session), equipment.step_needs(exercise.slug).get(step.name, [])
    )
    warning = f"{step.name} needs {' and '.join(lacking)}, not in your kit." if lacking else None
    session.add(
        Event(
            kind=LEVEL_SET,
            payload={
                "exercise_id": exercise_id,
                "from_step_id": state.ladder_step_id,
                "to_step_id": step.id,
            },
        )
    )
    state.ladder_step_id = step.id
    return Move(MoveOutcome.LEVEL_SET, exercise.name, step.name, warning)


@dataclass(frozen=True)
class Ready:
    """An exercise ready to move up, with its slug for a link to its ladder (ADR-0075)."""

    exercise: str
    slug: str


@dataclass(frozen=True)
class Rung:
    """One step of an exercise's ladder."""

    id: int
    name: str
    cue: str | None
    missing: tuple[str, ...] = ()  # the kit it needs that isn't listed: locked (ADR-0071)


@dataclass(frozen=True)
class Point:
    """One session on a Progress graph."""

    day: date
    best: int  # the session's best set, as "best" counts it
    step_number: int  # 1-based, so the graph can mark a move up
    kg: float | None = None  # its heaviest set's weight, on a loaded step (ADR-0072)


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
    trend: tuple[Point, ...] = ()  # the last TREND_WEEKS, oldest first; only with ``on``
    slug: str = ""
    ladder: tuple[Rung, ...] = ()  # every step, easiest first
    unlock: str | None = None  # on the last step the kit allows: what opens the next one


TREND_WEEKS = 6  # the Progress graphs' window: long enough to see a change, short enough to feel it


def _trend(
    session: Session, exercise_id: int, per_side: bool, block: BlockKind | None, since: date
) -> tuple[Point, ...]:
    """The best set of each done session since ``since``, oldest first, across ladder steps."""
    query = (
        select(
            SetLog.workout_id,
            Workout.local_date,
            LadderStep.position,
            SetLog.set_no,
            SetLog.side,
            SetLog.value,
            SetLog.load_kg,
        )
        .join(Workout)
        .join(LadderStep, LadderStep.id == SetLog.ladder_step_id)
        .where(
            Workout.status == WorkoutStatus.DONE,
            SetLog.exercise_id == exercise_id,
            Workout.local_date >= since,
        )
        .order_by(Workout.local_date, Workout.created_at, Workout.id)
    )
    if block is BlockKind.STRENGTH:
        query = query.where(Workout.block == BlockKind.STRENGTH)
    elif block is BlockKind.HYPERTROPHY:
        query = query.where(or_(Workout.block.is_(None), Workout.block != BlockKind.STRENGTH))
    days: dict[int, date] = {}
    steps: dict[int, int] = {}
    sets: dict[int, list[tuple[int, Side, int]]] = {}
    loads: dict[int, list[tuple[int, float]]] = {}
    for workout_id, on, position, set_no, side, value, kg in session.execute(query):
        days[workout_id] = on
        steps[workout_id] = max(steps.get(workout_id, 0), position)
        sets.setdefault(workout_id, []).append((set_no, Side(side), value))
        if kg is not None:
            loads.setdefault(workout_id, []).append((set_no, kg))
    return tuple(
        Point(
            days[w],
            max(combine_sides(sets[w], unilateral=per_side), default=0),
            steps[w] + 1,
            top_weight(loads.get(w, [])),
        )
        for w in days
    )


def overview(session: Session, on: date | None = None) -> list[Standing]:
    """Every exercise in plan order (first session it appears in), then any the plan doesn't
    use. Ready means ready under at least one of its prescriptions, as Move up checks. With
    ``on`` (today), each also has its trend over the last TREND_WEEKS."""
    since = on - timedelta(weeks=TREND_WEEKS) + timedelta(days=1) if on is not None else None
    order: dict[int, None] = {}
    for item in session.scalars(
        select(TemplateItem)
        .join(SessionTemplate)
        .order_by(SessionTemplate.position, TemplateItem.place != Place.HOME, TemplateItem.position)
    ):
        order.setdefault(item.exercise_id, None)
    for exercise_id in session.scalars(select(Exercise.id).order_by(Exercise.id)):
        order.setdefault(exercise_id, None)

    kit = equipment.kit(session)
    gym = user_settings.load(session).places is not Places.HOME
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
        trained = [i for i in items if gym or i.place == Place.HOME]
        if (exercise.retired or not trained) and not history:
            # Nothing to show for an exercise no longer trained (#107), or one in no session
            # the person trains and never logged: only at the gym, for someone who trains at
            # home (ADR-0071), or in no session at all yet (ADR-0072).
            continue
        statuses = {_status(session, item, step, kit) for item in items}
        needs = equipment.ladder_needs(exercise)
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
                trend=_trend(session, exercise_id, per_side, block, since)
                if since is not None
                else (),
                slug=exercise.slug,
                ladder=tuple(
                    Rung(r.id, r.name, r.cue, tuple(kit_rules.missing(kit, n)))
                    for r, n in zip(exercise.ladder, needs, strict=True)
                ),
                unlock=_unlock(step, kit),
            )
        )
    return result


def ready(standings: list[Standing]) -> list[Ready]:
    """The exercises ready to move up, in plan order."""
    return [Ready(s.exercise, s.slug) for s in standings if s.status is Progress.READY]
