"""Which training block a day is in (ADR-0028), from the settings and the pause history."""

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, Exercise, LadderStep, TemplateItem
from training_coach.domain import locks
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
from training_coach.domain.load import LoadKit
from training_coach.domain.places import no_kit_step
from training_coach.domain.retests import block_start
from training_coach.domain.targets import Prescription
from training_coach.services import step_locks, users
from training_coach.services.seed import bundled_plan


def current(session: Session, on: date, tz: ZoneInfo) -> Block | None:
    """The block ``on`` falls in, or None when blocks are off."""
    found = _started_and_paused(session, on, tz)
    return None if found is None else block_on(on, *found)


def start(session: Session, on: date, tz: ZoneInfo) -> date | None:
    """The first day of the block ``on`` falls in, or None when blocks are off (#95)."""
    found = _started_and_paused(session, on, tz)
    return None if found is None else block_start(on, *found)


def _started_and_paused(session: Session, on: date, tz: ZoneInfo) -> tuple[date, set[date]] | None:
    """When blocks started and the days paused since, up to ``on``; None when blocks are off."""
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
    return row.blocks_started_on, paused_days(changes, until=on)


def strength_applies(block: Block | None, session_kind: str | None) -> bool:
    """Whether a session gets the strength prescription: strength sessions in strength blocks."""
    return block is not None and block.kind is BlockKind.STRENGTH and session_kind == "strength"


def load_kit(slug: str, step: str) -> LoadKit | None:
    """What carries the weight when this step of this exercise takes load (ADR-0072), from the
    bundled plan like the summary; None for a step without load."""
    return _load_kits().get((slug, step))


def loadable(slug: str) -> bool:
    """Whether any step of this exercise takes load."""
    return any(found == slug for found, _ in _load_kits())


@lru_cache(maxsize=1)
def _load_kits() -> dict[tuple[str, str], LoadKit]:
    return {(e.slug, step): kit for e in bundled_plan().exercises for step, kit in e.loads.items()}


def _current_step(session: Session, exercise: Exercise) -> LadderStep:
    state = users.exercise_state(session, exercise.id)
    step = session.get(LadderStep, state.ladder_step_id) if state is not None else None
    # Seeding always creates state; fall back to the first rung if not.
    return step if step is not None else min(exercise.ladder, key=lambda s: s.position)


def step_for(
    session: Session,
    exercise: Exercise,
    strength: bool,
    *,
    at_gym: bool = False,
    away: bool = False,
) -> tuple[LadderStep, bool]:
    """The step trained and whether it's the top of its open steps with the tempo cue added:
    the next open step for rep-counted work under the strength prescription, else the current
    step. Locked steps are skipped as Move up skips them (kit at home, ADR-0071; what the person
    avoids, anywhere, ADR-0083); with none open above, the current step, with the cue. A loaded
    step stays: its strength block is 4-8 reps at a heavier weight (ADR-0072)."""
    current = _current_step(session, exercise)
    if not strength or ExerciseKind(exercise.kind) is not ExerciseKind.REPS:
        return current, False
    if load_kit(exercise.slug, current.name) is not None:
        return current, False
    ladder = list(exercise.ladder)
    at = next(i for i, s in enumerate(ladder) if s.id == current.id)
    limits = step_locks.limits(session, at_gym=at_gym, away=away)
    found = locks.next_open(step_locks.ladder(exercise), at, limits)
    return (ladder[found], False) if found is not None else (current, True)


def kit_free(session: Session, exercise: Exercise, step: LadderStep) -> LadderStep:
    """The step done away (ADR-0086): ``step`` when it is open with no kit at all and takes no
    load, else the highest step below it that is (the kit-lock rule with an empty kit, ADR-0071,
    and what the person avoids, ADR-0083); ``step`` when none is."""
    ladder = list(exercise.ladder)
    at = next(i for i, s in enumerate(ladder) if s.id == step.id)
    limits = step_locks.limits(session, away=True)
    free = [
        locks.lock(asks, limits).open and load_kit(exercise.slug, rung.name) is None
        for rung, asks in zip(ladder, step_locks.ladder(exercise), strict=True)
    ]
    return ladder[no_kit_step(free, at)]


@dataclass(frozen=True)
class Assignment:
    """What one planned exercise asks for today (ADR-0028)."""

    step: LadderStep
    cue: str | None
    prescription: Prescription
    history: BlockKind | None  # which block's sessions its targets come from
    # Away, the step was lowered to one that needs no kit, for today only (ADR-0086).
    no_kit: bool = False


def assign(
    session: Session,
    item: TemplateItem,
    strength: bool,
    chosen: LadderStep | None = None,
    *,
    at_gym: bool = False,
    away: bool = False,
) -> Assignment:
    """``chosen``: a level picked for today in the session (ADR-0080), trained as it is: no
    step harder in a strength block, as the person picked the step they do. ``at_gym``: the
    home kit locks nothing there (ADR-0071). ``away``: with no equipment, a step that needs kit
    gives way to the highest one below it that needs none (ADR-0086); the level stays."""
    kind = ExerciseKind(item.exercise.kind)
    step, at_top = (
        (chosen, False)
        if chosen is not None
        else step_for(session, item.exercise, strength, at_gym=at_gym, away=away)
    )
    no_kit = False
    if away and chosen is None:
        lowered = kit_free(session, item.exercise, step)
        if lowered.id != step.id:
            step, at_top, no_kit = lowered, False, True
    if not strength or kind is not ExerciseKind.REPS:
        return Assignment(
            step=step,
            cue=step.cue,
            prescription=Prescription(item.sets, item.rep_min, item.rep_max, kind),
            history=history_kind(kind, BlockKind.HYPERTROPHY),
            no_kit=no_kit,
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
        no_kit=no_kit,
    )
