"""Feedback after a save, and moving up the ladder (step 1-G; ADR-0016, ADR-0025, ADR-0075).

``feedback`` reports new personal bests and the progression status of each exercise in a saved
workout. ``move_up`` and ``not_yet`` answer the "ready to progress" prompt; ``move_up`` checks
everything again when pressed, so a stale or forged press changes nothing. ``set_level`` puts an
exercise on any step of its own ladder by hand, ready or not (ADR-0075). The caller owns the
transaction.

Steps lock by kit (ADR-0071) and by what the person has chosen to avoid (ADR-0083, through
``step_locks``): Move up goes to the next open step; past the last one the exercise is at the top
of its open steps, and ``unlock`` names the kit that opens the next, when kit can. A locked level
can still be chosen by hand, with a warning.

Stepping down is suggested, never done for the person (ADR-0084): ``Down`` says when the bottom of
the range was out of reach twice; ``step_down`` applies the step below as a by-hand change once
the rule is checked again, and ``not_yet_down`` dismisses the suggestion until a new session at
the step meets the rule again.
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
from training_coach.domain import locks
from training_coach.domain.blocks import BlockKind, history_kind
from training_coach.domain.enums import ExerciseKind, Place, Places, Side, WorkoutStatus
from training_coach.domain.load import top_weight
from training_coach.domain.locks import Limits
from training_coach.domain.muscles import Muscle
from training_coach.domain.progression import (
    Catalogued,
    Progress,
    StepDown,
    assess,
    combine_sides,
    easier_exercises,
    judged_sessions,
)
from training_coach.domain.progression import step_down as step_down_rule
from training_coach.domain.queue import local_date
from training_coach.domain.records import NewBests, new_bests
from training_coach.domain.targets import Pace, Prescription
from training_coach.services import blocks, step_locks, user_settings, users
from training_coach.services.seed import bundled_plan

TOP_NOTED = "progress.top_of_ladder"
# Said where every harder step is locked, on every surface, without saying why (ADR-0083)
NO_OPEN_STEP = "no open step above this one"
NO_LIMITS = Limits()  # nothing listed, nothing avoided: no step locks
LEVEL_SET = "progress.level_set"
NOT_YET_DOWN = "progress.not_yet_down"  # a step-down suggestion dismissed (ADR-0084)
# Each Not yet to a step down: (exercise id, step id, newest session the rule judged then)
Dismissals = frozenset[tuple[int, int, int | None]]
DISMISSAL_KEYS = ("exercise_id", "step_id", "workout_id")


@dataclass(frozen=True)
class Down:
    """The bottom of the range out of reach twice (ADR-0084): the step below to suggest, or at a
    ladder's first step (or with every step below locked by the kit) none, and the catalogue's
    easier exercises for the same muscles. Only a suggestion: the person decides."""

    step_id: int  # the step judged: Step down and Not yet send it back
    below: str | None  # the step below's name; None when there is none
    easier: tuple[str, ...] = ()  # with no step below: level 1-2 exercises sharing a prime mover


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
    load_kg: float | None = None  # the session's weight: its bests count only that (ADR-0072)
    # At the top with harder steps above, every one locked (kit, or what the person avoids):
    # said as "no open step above this one", never why (ADR-0083)
    capped: bool = False
    down: Down | None = None  # the step below, suggested (ADR-0084)


class MoveOutcome(StrEnum):
    MOVED = "moved"
    ALREADY_MOVED = "already_moved"  # the step changed since the prompt: nothing to do
    NOT_READY = "not_ready"
    NO_NEXT_STEP = "no_next_step"
    STRENGTH_BLOCK = "strength_block"  # moving up waits for the hypertrophy block (ADR-0028)
    STAYED = "stayed"  # Not yet, recorded
    LEVEL_SET = "level_set"  # put on a step by hand (ADR-0075)
    SAME_LEVEL = "same_level"  # already on that step: nothing to do
    STEPPED_DOWN = "stepped_down"  # the step below, chosen from the suggestion (ADR-0084)
    NO_STEP_BELOW = "no_step_below"  # the first step, or every step below is locked
    STAYED_DOWN = "stayed_down"  # Not yet to a step down, recorded


@dataclass(frozen=True)
class Move:
    outcome: MoveOutcome
    exercise: str
    step: str | None = None  # the step trained from now on, when moved
    warning: str | None = None  # a locked level chosen by hand, in words (ADR-0071, ADR-0083)


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


def planned_sets(session: Session, slug: str, workout_ids: Sequence[int]) -> list[int | None]:
    """The sets each workout planned of the exercise ``slug``, in the order given (ADR-0084):
    None for a workout without a plan (a typed log, or saved before plans were kept) or whose
    plan doesn't name the exercise, which planned every set."""
    query = select(Workout.id, Workout.planned).where(Workout.id.in_(workout_ids))
    found = dict(session.execute(query).all())
    counts: list[int | None] = []
    for workout_id in workout_ids:
        entry = (found.get(workout_id) or {}).get(slug)
        sets = entry.get("sets") if isinstance(entry, dict) else None
        counts.append(sets if isinstance(sets, int) and sets >= 0 else None)
    return counts


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


def _at(step: LadderStep) -> tuple[list[LadderStep], int]:
    ladder = step.exercise.ladder
    return ladder, next(i for i, s in enumerate(ladder) if s.id == step.id)


def _next_step(step: LadderStep, limits: Limits) -> LadderStep | None:
    """The next open step: Move up skips the locked ones (ADR-0071, ADR-0083)."""
    ladder, at = _at(step)
    found = locks.next_open(step_locks.ladder(step.exercise), at, limits)
    return ladder[found] if found is not None else None


def _unlock(step: LadderStep, limits: Limits) -> str | None:
    """At the top for the kit: "a 16 kg kettlebell unlocks One-arm, 16 kg"; else None. Never
    names what the person avoids: this is said on Telegram and to their AI too."""
    ladder, at = _at(step)
    found = locks.unlocks_next(step_locks.ladder(step.exercise), at, limits)
    if found is None:
        return None
    index, lacking = found
    return f"{' and '.join(lacking)} unlocks {ladder[index].name}"


def _below_top(step: LadderStep) -> bool:
    """Whether harder steps exist above ``step`` on its ladder, open or not."""
    ladder, at = _at(step)
    return at < len(ladder) - 1


def step_below(step: LadderStep, limits: Limits) -> LadderStep | None:
    """The nearest open step below: a step down skips the locked ones (ADR-0084)."""
    ladder, at = _at(step)
    found = locks.previous_open(step_locks.ladder(step.exercise), at, limits)
    return ladder[found] if found is not None else None


def _skipped(session: Session, slug: str, step_id: int, workout_ids: Sequence[int]) -> list[bool]:
    """Per workout, in the order given: whether the step-down rule passes it over (ADR-0084), a
    strength-block session or one that did ``slug`` at ``step_id`` for today only (ADR-0080)."""
    query = select(Workout.id, Workout.block, Workout.planned).where(Workout.id.in_(workout_ids))
    found = {w: (block, planned) for w, block, planned in session.execute(query)}
    skipped = []
    for workout_id in workout_ids:
        block, planned = found.get(workout_id, (None, None))
        entry = (planned or {}).get(slug)
        today = entry.get("today") if isinstance(entry, dict) else None
        skipped.append(block == BlockKind.STRENGTH or today == step_id)
    return skipped


def _down_rule(
    session: Session, item: TemplateItem, step: LadderStep, limits: Limits, pace: Pace
) -> tuple[StepDown, int | None]:
    """The step-down rule for one prescription, and the newest session it judged (what a Not
    yet dismisses), None when it judged none."""
    if blocks.load_kit(step.exercise.slug, step.name) is not None:
        return StepDown.NONE, None  # the weight is what to lower (ADR-0072)
    block = history_kind(ExerciseKind(item.exercise.kind), BlockKind.HYPERTROPHY)
    done = sessions_at_step(session, step.exercise_id, step.id, item.per_side, block)
    ids = [w for w, _ in done]
    skipped = _skipped(session, step.exercise.slug, step.id, ids)
    found = step_down_rule(
        _prescription(item),
        [v for _, v in done],
        has_step_below=step_below(step, limits) is not None,
        pace=pace,
        planned=planned_sets(session, step.exercise.slug, ids),
        skipped=skipped,
    )
    latest = judged_sessions(len(ids), skipped)
    return found, ids[latest[0]] if latest else None


def dismissals(session: Session) -> Dismissals:
    """Every Not yet to a step down, read once per call that judges many exercises
    (``overview``, ``feedback``) rather than once per exercise."""
    found: set[tuple[int, int, int | None]] = set()
    for p in session.scalars(select(Event.payload).where(Event.kind == NOT_YET_DOWN)):
        if isinstance(p, dict):
            exercise_id, step_id, workout_id = (p.get(k) for k in DISMISSAL_KEYS)
            if isinstance(exercise_id, int) and isinstance(step_id, int):
                judged = workout_id if isinstance(workout_id, int) else None
                found.add((exercise_id, step_id, judged))
    return frozenset(found)


def easier(slug: str) -> tuple[str, ...]:
    """The bundled catalogue's exercises starting at level 1 or 2 that share a prime mover with
    ``slug``, for a ladder's first step (ADR-0083, ADR-0084)."""
    plan = bundled_plan().exercises
    mine = next((e for e in plan if e.slug == slug), None)
    if mine is None:
        return ()
    catalogue = [
        Catalogued(e.name, _primes(e.muscles), e.levels.get(e.ladder[0]))
        for e in plan
        if e.slug != slug and not e.retired
    ]
    return tuple(easier_exercises(_primes(mine.muscles), catalogue))


def _primes(muscles: dict[Muscle, float]) -> frozenset[str]:
    return frozenset(m for m, weight in muscles.items() if weight == 1)


def down(
    session: Session,
    items: Sequence[TemplateItem],
    step: LadderStep,
    limits: Limits,
    dismissed: Dismissals | None = None,
) -> Down | None:
    """The step-down suggestion for the exercise on ``step``, under any of its prescriptions;
    None when the rule isn't met, or a Not yet dismissed it for the session it last judged.
    ``dismissed``: the ``dismissals`` already read, when judging many exercises."""
    pace = user_settings.load(session).pace
    if dismissed is None:
        dismissed = dismissals(session)
    for item in items:
        found, latest = _down_rule(session, item, step, limits, pace)
        if found is StepDown.NONE or (step.exercise_id, step.id, latest) in dismissed:
            continue
        below = step_below(step, limits)
        if below is not None:
            return Down(step.id, below.name)
        return Down(step.id, None, easier(step.exercise.slug))
    return None


def _status(
    session: Session, item: TemplateItem | None, step: LadderStep, limits: Limits = NO_LIMITS
) -> Progress:
    if item is None or blocks.load_kit(step.exercise.slug, step.name) is not None:
        # A loaded step gets harder by weight, suggested on the set screen (ADR-0072).
        return Progress.HOLD
    # Readiness is judged on the hypertrophy prescription and its history (ADR-0028).
    block = history_kind(ExerciseKind(item.exercise.kind), BlockKind.HYPERTROPHY)
    done = sessions_at_step(session, step.exercise_id, step.id, item.per_side, block)
    # A shorter day is judged on the sets it planned (ADR-0084).
    planned = planned_sets(session, step.exercise.slug, [w for w, _ in done])
    upcoming = _next_step(step, limits)
    return assess(_prescription(item), [v for _, v in done], upcoming is not None, planned=planned)


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

    # Kit locks apply at home only: a gym has everything (ADR-0071). What the person avoids
    # applies anywhere (ADR-0083).
    limits = step_locks.limits(session, at_gym=workout.place != Place.HOME)
    dismissed = dismissals(session)
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
        status = _status(session, item, step, limits) if on_current else Progress.HOLD
        # A step down is judged on the step trained now; strength-block sessions are passed
        # over inside the rule, so a block doesn't hold it (ADR-0084).
        at_level = state is not None and state.ladder_step_id == step_id
        suggested = (
            down(session, [item], step, limits, dismissed)
            if at_level and item is not None
            else None
        )
        upcoming = _next_step(step, limits) if status is Progress.READY else None
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
                unlock=_unlock(step, limits) if status is Progress.TOP_OF_LADDER else None,
                load_kg=weight,
                capped=status is Progress.TOP_OF_LADDER and _below_top(step),
                down=suggested,
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
    limits = step_locks.limits(session)
    upcoming = _next_step(step, limits)
    if upcoming is None:  # the last step, or the last one open
        return Move(MoveOutcome.NO_NEXT_STEP, exercise.name)
    if not any(
        _status(session, item, step, limits) is Progress.READY
        for item in _items(session, exercise_id)
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
    # A locked step is still the person's to choose: say so, don't refuse.
    warning = step_locks.warning(session, step)
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


def _on(
    session: Session, exercise_id: int, step_id: int
) -> tuple[Exercise, LadderStep] | Move | None:
    """The exercise and step a step-down answer names; ALREADY_MOVED when the exercise isn't on
    that step any more; None when either doesn't exist or the step isn't on its ladder."""
    exercise = session.get(Exercise, exercise_id)
    state = users.exercise_state(session, exercise_id)
    step = session.get(LadderStep, step_id)
    if exercise is None or state is None or step is None or step.exercise_id != exercise_id:
        return None
    if state.ladder_step_id != step_id:
        return Move(MoveOutcome.ALREADY_MOVED, exercise.name)
    return exercise, step


def step_down(session: Session, exercise_id: int, from_step_id: int) -> Move | None:
    """Step down from the suggestion (ADR-0084): the nearest open step below ``from_step_id``,
    set as a by-hand change (``set_level``, its event logged). Checked again now, as Move up is,
    so a stale or forged press changes nothing: the exercise must still be on ``from_step_id``
    (else ALREADY_MOVED) and the suggestion must still stand (else NOT_READY: a Not yet or a
    newer session has removed it). None for an exercise or step that doesn't exist."""
    found = _on(session, exercise_id, from_step_id)
    if not isinstance(found, tuple):
        return found
    exercise, step = found
    limits = step_locks.limits(session)
    suggested = down(session, _items(session, exercise_id), step, limits)
    if suggested is None:
        return Move(MoveOutcome.NOT_READY, exercise.name)
    below = step_below(step, limits)
    if below is None:
        return Move(MoveOutcome.NO_STEP_BELOW, exercise.name, step.name)
    moved = set_level(session, exercise_id, below.id)
    warning = moved.warning if moved is not None else None
    return Move(MoveOutcome.STEPPED_DOWN, exercise.name, below.name, warning)


def not_yet_down(session: Session, exercise_id: int, step_id: int) -> Move | None:
    """Not yet to a step down: stay, and don't suggest it again until a new session at the step
    meets the rule. Recorded only while the exercise is still on ``step_id``. None for an
    exercise or step that doesn't exist."""
    found = _on(session, exercise_id, step_id)
    if not isinstance(found, tuple):
        return found
    exercise, step = found
    pace = user_settings.load(session).pace
    limits = step_locks.limits(session)
    judged = (
        _down_rule(session, item, step, limits, pace)[1] for item in _items(session, exercise_id)
    )
    latest = next((w for w in judged if w is not None), None)
    session.add(
        Event(
            kind=NOT_YET_DOWN,
            payload={"exercise_id": exercise_id, "step_id": step_id, "workout_id": latest},
        )
    )
    return Move(MoveOutcome.STAYED_DOWN, exercise.name, step.name)


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
    # "Can you do ...?": a yes says the person can start here (G1, ADR-0075); None on the
    # first step, which anyone can start at
    question: str | None = None
    # What it asks that the person has chosen to avoid, in words: locked too (ADR-0083)
    avoided: tuple[str, ...] = ()


def rung(step: LadderStep, lock: locks.Lock, question: str | None = None) -> Rung:
    """One step of a ladder, with why it is locked for this person."""
    return Rung(step.id, step.name, step.cue, lock.missing, question, lock.avoided)


def step_questions(slug: str) -> dict[str, str]:
    """Ladder step name -> its level question, for one exercise of the bundled plan."""
    found = next((e for e in bundled_plan().exercises if e.slug == slug), None)
    return dict(found.questions) if found is not None else {}


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
    last_kg: tuple[float | None, ...] = ()  # each of ``last``'s sets' weight, None without one
    # The weight of the session that set ``best_set``, its heaviest set's (ADR-0072): the best
    # counts every weight, so it says which, as the weekly review does. None without one.
    best_kg: float | None = None
    down: Down | None = None  # the step below, suggested (ADR-0084)

    @property
    def capped(self) -> bool:
        """At the top with harder steps above, every one locked: "no open step above this
        one", never why (ADR-0083)."""
        return self.status is Progress.TOP_OF_LADDER and self.step_number < self.steps


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


def _set_loads(
    session: Session, exercise_id: int, step_id: int, workout_ids: Sequence[int]
) -> dict[int, dict[int, float]]:
    """Each set's weight by workout and set number, at this step: one for both sides of a set,
    the heavier if they ever differ. A workout or set without a weight is missing."""
    rows = session.execute(
        select(SetLog.workout_id, SetLog.set_no, SetLog.load_kg).where(
            SetLog.workout_id.in_(workout_ids),
            SetLog.exercise_id == exercise_id,
            SetLog.ladder_step_id == step_id,
            SetLog.load_kg.is_not(None),
        )
    )
    found: dict[int, dict[int, float]] = {}
    for workout_id, set_no, kg in rows:
        sets = found.setdefault(workout_id, {})
        if kg is not None:
            sets[set_no] = max(kg, sets.get(set_no, kg))
    return found


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

    limits = step_locks.limits(session)
    dismissed = dismissals(session)
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
        done = sessions_at_step(session, exercise_id, step.id, per_side, block)
        history = [v for _, v in done]
        trained = [i for i in items if gym or i.place == Place.HOME]
        if (exercise.retired or not trained) and not history:
            # Nothing to show for an exercise no longer trained (#107), or one in no session
            # the person trains and never logged: only at the gym, for someone who trains at
            # home (ADR-0071), or in no session at all yet (ADR-0072).
            continue
        statuses = {_status(session, item, step, limits) for item in items}
        asks = step_locks.ladder(exercise)
        questions = step_questions(exercise.slug)
        status = next(
            (s for s in (Progress.READY, Progress.TOP_OF_LADDER) if s in statuses), Progress.HOLD
        )
        best = max((max(v, default=0) for v in history), default=None)
        # The session that set the best: the first to reach it, as a tie is no new best. The
        # history is newest first.
        setter = next((w for w, v in reversed(done) if max(v, default=0) == best), None)
        latest = done[0][0] if done else None
        loads = _set_loads(
            session, exercise_id, step.id, [w for w in (latest, setter) if w is not None]
        )
        at_last = loads.get(latest, {}) if latest is not None else {}
        at_best = loads.get(setter, {}) if setter is not None else {}
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
                best_set=best,
                status=status,
                retired=exercise.retired,
                trend=_trend(session, exercise_id, per_side, block, since)
                if since is not None
                else (),
                slug=exercise.slug,
                ladder=tuple(
                    rung(r, locks.lock(a, limits), questions.get(r.name))
                    for r, a in zip(exercise.ladder, asks, strict=True)
                ),
                unlock=_unlock(step, limits),
                last_kg=tuple(at_last.get(n) for n in range(1, len(history[0]) + 1))
                if history
                else (),
                best_kg=top_weight(list(at_best.items())),
                down=down(session, items, step, limits, dismissed)
                if not exercise.retired
                else None,
            )
        )
    return result


def ready(standings: list[Standing]) -> list[Ready]:
    """The exercises ready to move up, in plan order."""
    return [Ready(s.exercise, s.slug) for s in standings if s.status is Progress.READY]


def stepping_down(standings: list[Standing]) -> list[Ready]:
    """The exercises with a step down suggested (ADR-0084), in plan order."""
    return [Ready(s.exercise, s.slug) for s in standings if s.down is not None]


@dataclass(frozen=True)
class Top:
    """The ready rule met with no level to move to (ADR-0078): the top of the ladder, or of the
    levels the kit allows, when ``unlock`` says what opens the next one (ADR-0071)."""

    exercise: str
    slug: str
    unlock: str | None
    capped: bool = False  # harder steps exist, every one locked: never says why (ADR-0083)


def tops(session: Session, standings: list[Standing], since: date, tz: ZoneInfo) -> list[Top]:
    """The exercises still at the top that reached it on local day ``since`` or later, in plan
    order. Said once per level, as the saved screen says it: the first save there notes it."""
    noted = {
        (payload.get("exercise_id"), payload.get("step_id"))
        for at, payload in session.execute(
            select(Event.at, Event.payload).where(Event.kind == TOP_NOTED)
        )
        if isinstance(payload, dict) and local_date(at, tz) >= since
    }
    return [
        Top(s.exercise, s.slug, s.unlock, s.capped)
        for s in standings
        if s.status is Progress.TOP_OF_LADDER and (s.exercise_id, s.step_id) in noted
    ]
