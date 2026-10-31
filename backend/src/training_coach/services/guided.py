"""The guided session (D1, #117): today's session for the web app, one set at a time.

Which session today is follows the same rule as a typed log (``workout_log.target``): the one
picked today, else the one at the queue's pointer; once a planned session is done or rested
today, or held for tomorrow (Rest today or Push), there is none. Sets come in work order
(ADR-0031), with any pair swapped to start with its second exercise.

The exception is a conditioning session with more than its cardio (ADR-0066): once the cardio is
logged, however it was logged, the rest of that session stays open until the day ends, and its
sets are added to the day's workout.

Short on time today (ADR-0082): a strength or conditioning session runs at the minutes chosen
for the day, trimmed by ``domain.trim``. Items are never removed, so every set keeps its index:
a dropped item has no targets left. The set counts, the minutes and the person's pace are fixed
in the day's progress when its first set is kept, so nothing moves under the indexes after.
"""

import secrets
from collections.abc import Collection, Iterator, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Exercise,
    LadderStep,
    SessionProgress,
    SessionTemplate,
    SetLog,
    Workout,
)
from training_coach.domain import trim as trimming
from training_coach.domain.blocks import Block
from training_coach.domain.enums import ExerciseKind, Place, Side, WorkoutStatus
from training_coach.domain.load import MAX_KG, valid_kg
from training_coach.domain.muscles import Pattern
from training_coach.domain.parser import LIMITS, Entry
from training_coach.domain.rest import AFTER_PAIR_SECONDS, Kind, Rest, rests
from training_coach.domain.session_times import pace, plausible
from training_coach.domain.trim import WARM_UP, WarmUp
from training_coach.domain.work_order import SetRef, work_order
from training_coach.services import blocks, session_times, user_settings, users, workout_log
from training_coach.services.day_clash import Clash, Refused, Resolution
from training_coach.services.seed import bundled_plan
from training_coach.services.today import ItemPlan, SessionPlan, position, session_plan

SET_SECONDS = 45  # a rough working set, for the time estimate only
OPTIONS = (40, 30, 20)  # Short on time today (ADR-0082): the minutes offered besides as planned
TRIMMED = ("strength", "conditioning")  # recovery sessions run as planned (ADR-0082)


@dataclass(frozen=True)
class Length:
    """How long today's session runs (ADR-0082): the day's choice and what it does."""

    minutes: int | None  # chosen for the day; None: as planned
    keep: tuple[str, ...]  # exercise slugs pinned with Keep: never dropped
    planned: int  # about how long as planned, warm-up included
    trimmed: trimming.Trimmed  # each item's sets (0: dropped), the warm-up, the estimate
    pace: float  # the person's time on this session over its plain estimate; 1.0 unknown
    fixed: bool = False  # a set is kept: the length no longer changes


@dataclass(frozen=True)
class GuidedSet:
    item: int  # index into items
    set_no: int  # from 1
    target: int
    rest: Rest  # after this set, adjustable during the rest (D1, ADR-0065)


@dataclass(frozen=True)
class Guided:
    day: date
    template_id: int
    name: str
    focus: str
    kind: str  # strength | conditioning | recovery
    warm_up: bool
    block: Block | None
    minutes: int  # about how long, warm-up included
    rest_seconds: int  # the rest after a pair; each set carries its own (ADR-0065)
    items: tuple[ItemPlan, ...]
    order: tuple[GuidedSet, ...]
    slug: str = ""  # the session template's
    after_run: bool = False  # what's left of a conditioning session once its cardio is logged
    place: Place = Place.HOME  # where it is done: its home or gym version (ADR-0071)
    switch: bool = False  # Today offers Home | Gym
    length: Length | None = None  # short on time today (ADR-0082); None: never trimmed


def _kinds(items: tuple[ItemPlan, ...]) -> list[Kind | None]:
    """What the rest rules need about each item, from the catalogue (ADR-0064)."""
    catalogue = {e.slug: e for e in bundled_plan().exercises}
    kinds: list[Kind | None] = []
    for item in items:
        found = catalogue.get(item.slug)
        if found is None:  # not in the bundled plan: rests as a small exercise
            kinds.append(None)
        else:
            primes = frozenset(m for m, weight in found.muscles.items() if weight == 1)
            involved = frozenset(m for m, weight in found.muscles.items() if weight >= 0.5)
            kinds.append(Kind(found.pattern, primes, involved))
    return kinds


def work_groups(items: tuple[ItemPlan, ...], first: Collection[int] = ()) -> list[list[SetRef]]:
    """The session's sets in the order they're done, for the guided session and the bot's work
    list alike: no exercise twice in a row where a pair can avoid it, then no main muscle."""
    primes = [kind.primes if kind is not None else frozenset[str]() for kind in _kinds(items)]
    return work_order([len(i.targets) for i in items], [i.pair for i in items], first, primes)


def _ordered(items: tuple[ItemPlan, ...], groups: list[list[SetRef]]) -> tuple[GuidedSet, ...]:
    """The sets in work order, each with the rest that follows it (ADR-0065)."""
    flat = [ref for group in groups for ref in group]
    after = rests(groups, _kinds(items))
    return tuple(
        GuidedSet(item, set_no, items[item].targets[set_no - 1], rest)
        for (item, set_no), rest in zip(flat, after, strict=True)
    )


def _minutes(items: tuple[ItemPlan, ...], order: tuple[GuidedSet, ...], warm_up: bool) -> int:
    """About how long: each set's work and the rest after it, by the rules the session runs."""
    return round(_seconds(items, order) / 60) + (WARM_UP[WarmUp.FULL] if warm_up else 0)


def _seconds(items: tuple[ItemPlan, ...], order: tuple[GuidedSet, ...]) -> int:
    """Each set's work and the rest after it, warm-up not included."""
    seconds = 0
    for done in order:
        item = items[done.item]
        sides = 2 if item.per_side else 1
        if item.kind is ExerciseKind.DURATION_MIN:
            seconds += done.target * 60
        elif item.kind is ExerciseKind.SECONDS:
            seconds += done.target * sides
        else:
            seconds += SET_SECONDS * sides
        seconds += done.rest.seconds
    return seconds


# ---------------------------------------------------------------- short on time (ADR-0082)


def _cut(
    items: tuple[ItemPlan, ...], sets: Sequence[int], durations: Sequence[int | None]
) -> tuple[ItemPlan, ...]:
    """``items`` with each one's first ``sets`` targets (none: dropped) and a duration item's
    minutes at most its ``durations``. Nothing is removed, so indexes stay."""
    out = []
    for item, count, minutes in zip(items, sets, durations, strict=True):
        targets = item.targets[:count]
        if minutes is not None:
            targets = tuple(min(target, minutes) for target in targets)
        if targets == item.targets:
            out.append(item)
            continue
        load = replace(item.load, kg=item.load.kg[:count]) if item.load is not None else None
        out.append(replace(item, targets=targets, load=load))
    return tuple(out)


def _shapes(items: tuple[ItemPlan, ...], keep: Collection[str]) -> tuple[trimming.Item, ...]:
    """What the trim needs about each item, from the catalogue as the rests read it: an
    exercise it doesn't know is small work. Cardio counted in minutes can shorten."""
    shapes = []
    for item, kind in zip(items, _kinds(items), strict=True):
        pattern = kind.pattern if kind is not None else Pattern.ISOLATION
        timed = item.kind is ExerciseKind.DURATION_MIN and pattern is Pattern.CARDIO
        shapes.append(
            trimming.Item(
                sets=len(item.targets),
                pattern=pattern,
                primes=kind.primes if kind is not None else frozenset(),
                minutes=max(item.targets) if timed and item.targets else None,
                keep=item.slug in keep,
            )
        )
    return tuple(shapes)


def _estimator(items: tuple[ItemPlan, ...], first: Collection[int], at: float) -> trimming.Estimate:
    """Minutes of work for given set counts and durations, warm-up not included: the real
    order and rests over the cut items, at the person's pace ``at``."""

    def estimate(sets: tuple[int, ...], durations: tuple[int | None, ...]) -> float:
        cut = _cut(items, sets, durations)
        return _seconds(cut, _ordered(cut, work_groups(cut, first))) / 60 * at

    return estimate


@dataclass(frozen=True)
class _Fixed:
    """The length kept when the first set was (ADR-0082)."""

    minutes: int | None
    sets: tuple[int, ...]
    durations: tuple[int | None, ...]
    dropped: tuple[int, ...]
    pace: float
    ramp: bool = False  # ramp sets replaced the warm-up


def _fixed(row: SessionProgress | None, count: int) -> _Fixed | None:
    """The length fixed in ``row`` for a session of ``count`` items; None before the first set,
    or when the plan has changed shape since (it is worked out afresh then)."""
    found = row.fixed if row is not None else None
    if not isinstance(found, dict) or len(found.get("sets", ())) != count:
        return None
    return _Fixed(
        minutes=found.get("minutes"),
        sets=tuple(found["sets"]),
        durations=tuple(found["durations"]),
        dropped=tuple(found["dropped"]),
        pace=float(found["pace"]),
        ramp=found.get("warm_up") == WarmUp.RAMP.value,
    )


def _choice(
    row: SessionProgress | None, default: int | None = None
) -> tuple[int | None, tuple[str, ...]]:
    """The day's minutes and Keep pins as chosen in ``row``; with no choice made yet,
    ``default`` minutes (as planned until minutes per session is a setting, ADR-0082)."""
    found = row.length if row is not None else None
    if not isinstance(found, dict):
        return default, ()
    minutes = found.get("minutes")
    keep = tuple(slug for slug in found.get("keep", ()) if isinstance(slug, str))
    return (minutes if minutes in OPTIONS else None), keep


def _pace(
    session: Session,
    plan: SessionPlan,
    shapes: tuple[trimming.Item, ...],
    plain: trimming.Estimate,
    after_run: bool,
) -> float:
    """The person's pace on this session at its place (ADR-0082): their usual time done as
    planned over its plain estimate. The block after a run has no usual of its own."""
    if after_run:
        return 1.0
    totals = session_times.planned_totals(session, plan.template_id, plan.place)
    sets = tuple(s.sets for s in shapes)
    return pace(totals, plain(sets, tuple(s.minutes for s in shapes)))


def _length(
    session: Session,
    plan: SessionPlan,
    items: tuple[ItemPlan, ...],
    first: Collection[int],
    row: SessionProgress | None,
    after_run: bool,
) -> Length | None:
    """Today's length for ``plan`` (ADR-0082): None for a session that isn't trimmed. A
    strength block's prescription is in ``items`` already, so the trim comes after it."""
    if plan.kind not in TRIMMED:
        return None
    minutes, keep = _choice(row)
    shapes = _shapes(items, keep)
    fixed = _fixed(row, len(items))
    if fixed is not None:
        at = fixed.pace
    else:
        at = _pace(session, plan, shapes, _estimator(items, first, 1.0), after_run)
    estimate = _estimator(items, first, at)
    has_warm_up = plan.kind == "strength"
    planned = trimming.trim(shapes, None, estimate, has_warm_up=has_warm_up)
    if fixed is None:
        trimmed = trimming.trim(shapes, minutes, estimate, has_warm_up=has_warm_up)
    else:
        minutes = fixed.minutes
        how = trimming.warm_up(shapes, fixed.sets, minutes) if has_warm_up else WarmUp.NONE
        total = round(estimate(fixed.sets, fixed.durations)) + WARM_UP[how]
        fits = minutes is None or total <= minutes
        trimmed = trimming.Trimmed(fixed.sets, fixed.durations, fixed.dropped, how, total, fits)
    started = row is not None and (row.fixed is not None or bool(row.sets))
    return Length(minutes, keep, planned.minutes, trimmed, at, started)


def _fix(length: Length) -> dict[str, Any]:
    """``length`` as kept in ``session_progress.fixed`` when the first set is (ADR-0082)."""
    trimmed = length.trimmed
    return {
        "minutes": length.minutes,
        "sets": list(trimmed.sets),
        "durations": list(trimmed.durations),
        "dropped": list(trimmed.dropped),
        "pace": length.pace,
        "warm_up": trimmed.warm_up.value,
    }


def today(session: Session, on: date, tz: ZoneInfo, first: Collection[int] = ()) -> Guided | None:
    """Today's session to guide, or None when there is nothing planned left today. ``first``
    holds the pair numbers to start with their second exercise."""
    template = workout_log.target(session, on, tz)
    if template is None:
        return _after_run(session, on, tz, first)
    if held_today(session, on):
        return None
    block = blocks.current(session, on, tz)
    plan = session_plan(session, template.id, block, chosen(session, on, template.id, False))
    assert plan is not None  # noqa: S101 - target() returned this template a moment ago
    return _guided(session, on, plan, plan.items, block, first, after_run=False)


def at_length(session: Session, on: date, plan: SessionPlan) -> tuple[SessionPlan, Length | None]:
    """``plan`` as it runs on ``on`` (ADR-0082), for the bot's work list: its items cut to the
    day's length once minutes are chosen for it in the app (a dropped item keeps its place
    with no targets), and that length. None for a session that isn't trimmed (recovery)."""
    row = _row(session, on)
    mine = row if _mine(row, plan, after_run=False) else None
    length = _length(session, plan, plan.items, (), mine, after_run=False)
    if length is None:
        return plan, None
    items = _cut(plan.items, length.trimmed.sets, length.trimmed.durations)
    return replace(plan, items=items), length


def chosen(session: Session, on: date, template_id: int, after_run: bool) -> dict[str, int]:
    """The levels chosen for today in ``on``'s guided session of ``template_id`` (ADR-0080),
    by exercise slug: none once that progress no longer belongs to the session shown."""
    row = _row(session, on)
    if row is None or row.template_id != template_id or row.after_run != after_run:
        return {}
    return dict(row.steps)


def _mine(row: SessionProgress | None, plan: SessionPlan, after_run: bool) -> bool:
    """Whether ``row`` is the progress of the session shown: its session, version and part."""
    return row is not None and (row.template_id, row.place, row.after_run) == (
        plan.template_id,
        plan.place,
        after_run,
    )


def _guided(
    session: Session,
    on: date,
    plan: SessionPlan,
    items: tuple[ItemPlan, ...],
    block: Block | None,
    first: Collection[int],
    *,
    after_run: bool,
) -> Guided:
    row = _row(session, on)
    mine = row if _mine(row, plan, after_run) else None
    length = _length(session, plan, items, first, mine, after_run)
    if length is not None:
        items = _cut(items, length.trimmed.sets, length.trimmed.durations)
    groups = work_groups(items, first)
    order = _ordered(items, groups)
    if length is not None:
        warm_up, minutes = length.trimmed.warm_up is WarmUp.FULL, length.trimmed.minutes
    else:
        warm_up = plan.kind == "strength"
        minutes = _minutes(items, order, warm_up)
    return Guided(
        day=on,
        template_id=plan.template_id,
        name=plan.name,
        focus=plan.focus,
        kind=plan.kind,
        slug=plan.slug,
        warm_up=warm_up,
        block=block,
        minutes=minutes,
        rest_seconds=AFTER_PAIR_SECONDS,
        items=items,
        order=order,
        after_run=after_run,
        place=plan.place,
        switch=plan.switch,
        length=length,
    )


def _run_done(session: Session, on: date) -> Workout | None:
    """The day's done conditioning session, the workout an after-run block is added to."""
    return session.scalar(
        select(Workout)
        .join(SessionTemplate, Workout.template_id == SessionTemplate.id)
        .where(
            Workout.local_date == on,
            Workout.status == WorkoutStatus.DONE,
            SessionTemplate.kind == "conditioning",
        )
        .order_by(Workout.id.desc())
        .limit(1)
    )


def _left(
    session: Session, workout: Workout, items: tuple[ItemPlan, ...]
) -> tuple[ItemPlan, ...] | None:
    """The session's items not logged in ``workout`` once its run is: None unless the session
    has exactly one cardio exercise (as ``cardio.planned`` reads it) and the workout logged it,
    so a conditioning session without a run, or saved short, offers nothing "after the run"."""
    cardio = {e.slug for e in bundled_plan().exercises if e.pattern == "cardio"}
    runs = [i.slug for i in items if i.slug in cardio]
    logged = set(
        session.scalars(
            select(Exercise.slug).join(SetLog).where(SetLog.workout_id == workout.id).distinct()
        )
    )
    if len(runs) != 1 or runs[0] not in logged:
        return None
    return tuple(i for i in items if i.slug not in cardio and i.slug not in logged)


def _after_run(session: Session, on: date, tz: ZoneInfo, first: Collection[int]) -> Guided | None:
    """What's left of the day's conditioning session once its cardio is logged (ADR-0066)."""
    workout = _run_done(session, on)
    if workout is None or workout.template_id is None:
        return None
    block = blocks.current(session, on, tz)
    plan = session_plan(
        session, workout.template_id, block, chosen(session, on, workout.template_id, True)
    )
    if plan is None:
        return None
    items = _left(session, workout, plan.items)
    return _guided(session, on, plan, items, block, first, after_run=True) if items else None


def held_today(session: Session, on: date) -> bool:
    """The queue's session was held for tomorrow today (Rest today or Push, ADR-0006): no
    training today. Only a hold of the session the queue still points at counts (a hold leaves
    the pointer on it), so a skipped row for any other session can't blank the day."""
    current = position(session)
    if current is None:
        return False
    query = select(Workout.id).where(
        Workout.local_date == on,
        Workout.status == WorkoutStatus.SKIPPED,
        Workout.template_id == current.pointer,
    )
    return session.scalar(query.limit(1)) is not None


# ---------------------------------------------------------------- progress and saving


@dataclass(frozen=True)
class Done:
    """A confirmed set: ``right`` only for one-sided exercises (None means the same as left).
    ``started_at`` and ``done_at``: when its screen appeared and when it was confirmed
    (ADR-0061), both or neither. ``load_kg``: the weight, on a loaded step only (ADR-0072).
    ``step_id``: the ladder step it was done at, set by the server when the exercise's level
    changes later in the session (ADR-0080); None: the step the session has for it."""

    item: int
    set_no: int
    left: int
    right: int | None = None
    started_at: datetime | None = None
    done_at: datetime | None = None
    load_kg: float | None = None
    step_id: int | None = None


def _stored(done: Done) -> dict[str, Any]:
    """``done`` as kept in ``session_progress.sets`` (JSON), times as ISO text."""
    row: dict[str, Any] = {
        "item": done.item,
        "set_no": done.set_no,
        "left": done.left,
        "right": done.right,
    }
    if done.started_at is not None and done.done_at is not None:
        row["started_at"] = done.started_at.isoformat()
        row["done_at"] = done.done_at.isoformat()
    if done.load_kg is not None:
        row["load_kg"] = done.load_kg
    if done.step_id is not None:
        row["step_id"] = done.step_id
    return row


def _done(row: dict[str, Any]) -> Done:
    """A kept set back; rows kept before ADR-0061 have no times."""
    started, ended = row.get("started_at"), row.get("done_at")
    return Done(
        item=row["item"],
        set_no=row["set_no"],
        left=row["left"],
        right=row.get("right"),
        started_at=datetime.fromisoformat(started) if started else None,
        done_at=datetime.fromisoformat(ended) if ended else None,
        load_kg=row.get("load_kg"),
        step_id=row.get("step_id"),
    )


def _timed(done: Done, now: datetime) -> Done:
    """``done`` with its times in UTC, if both are there and plausible; without them otherwise."""
    if (
        done.started_at is None
        or done.done_at is None
        or not plausible(done.started_at, done.done_at, now)
    ):
        return replace(done, started_at=None, done_at=None)
    return replace(
        done, started_at=done.started_at.astimezone(UTC), done_at=done.done_at.astimezone(UTC)
    )


@dataclass(frozen=True)
class Kept:
    day: date
    template_id: int
    position: int
    first: tuple[int, ...]
    sets: tuple[Done, ...]
    saved: bool
    revision: int = 0
    after_run: bool = False  # kept for the block after a run (ADR-0066)
    place: Place = Place.HOME  # the version its sets were done in (ADR-0071)
    steps: tuple[tuple[str, int], ...] = ()  # levels chosen for today (ADR-0080): slug, step


@dataclass(frozen=True)
class Pending:
    day: date
    session: str
    sets: int


def _row(session: Session, day: date) -> SessionProgress | None:
    return session.scalar(select(SessionProgress).where(SessionProgress.local_date == day))


def progress_row(session: Session, day: date) -> SessionProgress | None:
    """``day``'s kept progress itself, for a change made during the session (ADR-0080)."""
    return _row(session, day)


def _kept(row: SessionProgress) -> Kept:
    return Kept(
        day=row.local_date,
        template_id=row.template_id,
        position=row.position,
        first=tuple(row.first),
        sets=tuple(_done(s) for s in row.sets),
        saved=row.saved_workout_id is not None,
        revision=row.revision,
        after_run=row.after_run,
        place=Place(row.place),
        steps=tuple(sorted(row.steps.items())),
    )


def kept(session: Session, day: date) -> Kept | None:
    """The progress kept for ``day``, if any."""
    row = _row(session, day)
    return _kept(row) if row is not None else None


def sets_problem(
    items: tuple[ItemPlan, ...], sets: Sequence[Done], loaded: Collection[int] = ()
) -> str | None:
    """What's wrong with ``sets`` against the plan's items, or None: each set is one the plan
    has, recorded once, with values in range and sides only where the exercise has them. A
    set done at an earlier level (ADR-0080) takes a weight only when its step is in ``loaded``
    (see ``loaded_steps``), whatever the step the session has now."""
    seen: set[tuple[int, int]] = set()
    for done in sets:
        if not 0 <= done.item < len(items):
            return "unknown exercise"
        item = items[done.item]
        if not 1 <= done.set_no <= len(item.targets):
            return f"{item.exercise} has no set {done.set_no}"
        if (done.item, done.set_no) in seen:  # a repeat would log a set the plan doesn't have
            return f"{item.exercise} set {done.set_no} is recorded twice"
        seen.add((done.item, done.set_no))
        limit = LIMITS[item.kind]
        values = [done.left] if done.right is None else [done.left, done.right]
        if any(not 0 <= v <= limit for v in values):
            return f"{item.exercise}: values must be 0 to {limit}"
        if done.right is not None and not item.per_side:
            return f"{item.exercise} isn't done one side at a time"
        weighted = item.load is not None if done.step_id is None else done.step_id in loaded
        if done.load_kg is not None and not weighted:
            return f"{item.exercise} isn't done with a weight"
        if done.load_kg is not None and not valid_kg(done.load_kg):
            return f"{item.exercise}: a weight is more than 0 and at most {MAX_KG:g} kg"
    return None


def loaded_steps(
    session: Session, items: tuple[ItemPlan, ...], sets: Sequence[Done]
) -> frozenset[int]:
    """The earlier levels ``sets`` were done at (ADR-0080) that take a weight: a set's weight
    is checked against the step it was done at, not the one the session has now."""
    found = set()
    for done in sets:
        if done.step_id is None or not 0 <= done.item < len(items):
            continue
        step = session.get(LadderStep, done.step_id)
        if step is not None and blocks.load_kit(items[done.item].slug, step.name) is not None:
            found.add(step.id)
    return frozenset(found)


def _problem(
    session: Session, plan: Guided, position: int, first: Sequence[int], sets: Sequence[Done]
) -> str | None:
    if not 0 <= position <= len(plan.order):
        return "position out of range"
    pairs = {item.pair for item in plan.items if item.pair is not None}
    if any(number not in pairs for number in first):
        return "no such pair"
    return sets_problem(plan.items, sets, loaded_steps(session, plan.items, sets))


STALE = "this session changed on another device; reload it"
SAVED = "this session is saved already"


def keep(
    session: Session,
    plan: Guided,
    revision: int,
    position: int,
    first: Sequence[int],
    sets: Sequence[Done],
    now: datetime | None = None,
) -> int | str:
    """Keep where the person is in today's guided session: the new revision, or a problem.

    Every value is checked against the plan: nothing from the browser is trusted. The browser
    names the ``revision`` it last saw (0 before any); if the kept one is newer (another device
    moved on), nothing is written and ``STALE`` is returned. A set's times are kept only when
    plausible at ``now`` (default: the clock's now; ADR-0061). A set already kept keeps the
    level it was done at (ADR-0080): the browser never sends it."""
    row = _row(session, plan.day)
    sets = _with_levels(row, plan, sets)
    problem = _problem(session, plan, position, first, sets)
    if problem is not None:
        return problem
    restart = row is not None and (
        row.after_run != plan.after_run or (plan.after_run and row.saved_workout_id is not None)
    )
    if row is not None and restart:
        # The day's cardio was logged (or that log undone): the run's progress, saved or not,
        # gives way to the block after it, which starts afresh (ADR-0066). So does a block
        # saved with some of it left: the rest is offered, and kept afresh.
        if revision != 0:
            return STALE
        session.delete(row)
        session.flush()
        row = None
    if row is not None and row.saved_workout_id is not None:
        return SAVED
    if row is not None and (row.template_id != plan.template_id or row.place != plan.place):
        if revision != 0:  # this browser still shows the old session: nothing is deleted
            return STALE
        # The day's session changed (a pick or swap) or its version did: start afresh.
        session.delete(row)
        session.flush()
        row = None
    if row is not None and row.revision != revision:
        return STALE
    try:
        with session.begin_nested():  # two devices starting at once: one wins, one is stale
            if row is None:
                if revision != 0:
                    return STALE
                row = SessionProgress(
                    local_date=plan.day,
                    template_id=plan.template_id,
                    token=secrets.token_hex(16),
                    revision=0,
                    after_run=plan.after_run,
                    place=plan.place,
                )
                session.add(row)
            row.revision += 1
            row.position = position
            row.first = sorted(set(first))
            at = now or datetime.now(UTC)
            row.sets = [_stored(_timed(done, at)) for done in sets]
            if row.sets and row.fixed is None and plan.length is not None:
                row.fixed = _fix(plan.length)  # fixed from the first set kept (ADR-0082)
            session.flush()
    except IntegrityError:
        return STALE
    return row.revision


def _with_levels(row: SessionProgress | None, plan: Guided, sets: Sequence[Done]) -> list[Done]:
    """``sets`` with the level each was done at, as kept for the session shown (ADR-0080)."""
    if (
        row is None
        or row.template_id != plan.template_id
        or row.after_run != plan.after_run
        or row.saved_workout_id is not None
    ):
        return list(sets)
    levels = {(s["item"], s["set_no"]): s["step_id"] for s in row.sets if s.get("step_id")}
    return [replace(d, step_id=levels.get((d.item, d.set_no), d.step_id)) for d in sets]


def set_levels(
    items: tuple[ItemPlan, ...], sets: Sequence[Done], steps: dict[str, int]
) -> tuple[tuple[str, int, int], ...]:
    """The step each logged set was done at when it isn't the exercise's current one (ADR-0080):
    the level a set was done at, else the level chosen for today. Numbered as the log is."""
    found = []
    for index, numbered in _numbered(sets):
        slug = items[index].slug
        for number, done in numbered:
            step = done.step_id if done.step_id is not None else steps.get(slug)
            if step is not None:
                found.append((slug, number, step))
    return tuple(found)


def _planned(row: SessionProgress, items: tuple[ItemPlan, ...]) -> tuple[tuple[str, int], ...]:
    """What the session planned, for the saved workout (ADR-0084): each item's sets as fixed
    for the day, else all of them. A cardio item run shorter planned none: its target was
    dropped, not missed (ADR-0082), so it neither counts as a miss nor toward moving up."""
    fixed = _fixed(row, len(items))
    if fixed is None:
        return tuple((item.slug, len(item.targets)) for item in items)
    return tuple(
        (item.slug, 0 if minutes is not None and minutes < max(item.targets, default=0) else n)
        for item, n, minutes in zip(items, fixed.sets, fixed.durations, strict=True)
    )


def _day_minutes(row: SessionProgress, items: tuple[ItemPlan, ...]) -> int | None:
    """The minutes chosen for the day, as fixed with the first set; None as planned, and None
    when the minutes changed nothing (no set cut, no cardio shortened, nothing dropped, the
    warm-up kept): that day is the session as planned and counts toward "usually"."""
    fixed = _fixed(row, len(items))
    if fixed is None:
        return None
    unchanged = (
        not fixed.dropped
        and not fixed.ramp
        and all(
            n == len(item.targets) and (minutes is None or minutes >= max(item.targets, default=0))
            for item, n, minutes in zip(items, fixed.sets, fixed.durations, strict=True)
        )
    )
    return None if unchanged else fixed.minutes


def _numbered(sets: Sequence[Done]) -> Iterator[tuple[int, list[tuple[int, Done]]]]:
    """Each exercise's confirmed sets in set order, numbered from 1 as the log numbers them. A
    skipped set isn't logged, so sets 1 and 3 done become sets 1 and 2 of the log."""
    by_item: dict[int, list[Done]] = {}
    for done in sorted(sets, key=lambda d: (d.item, d.set_no)):
        by_item.setdefault(done.item, []).append(done)
    for index, dones in by_item.items():
        yield index, list(enumerate(dones, start=1))


def entries(items: tuple[ItemPlan, ...], sets: Sequence[Done]) -> tuple[Entry, ...]:
    """The confirmed sets as log entries, per exercise in set order and numbered from 1."""
    entries = []
    for index, numbered in _numbered(sets):
        item = items[index]
        rows: list[tuple[int, Side, int]] = []
        loads = tuple((n, d.load_kg) for n, d in numbered if d.load_kg is not None)
        for number, done in numbered:
            if item.per_side:
                right = done.left if done.right is None else done.right
                rows += [(number, Side.LEFT, done.left), (number, Side.RIGHT, right)]
            else:
                rows.append((number, Side.BOTH, done.left))
        entries.append(Entry(item.slug, tuple(rows), loads))
    return tuple(entries)


def for_today(session: Session, steps: dict[str, int]) -> dict[str, int]:
    """The levels chosen for today only (ADR-0080): ``steps`` minus those that are the person's
    level, chosen from now on."""
    if not steps:
        return {}
    query = select(Exercise.slug, Exercise.id).where(Exercise.slug.in_(steps))
    ids = dict(session.execute(query).all())
    found = {}
    for slug, step_id in steps.items():
        state = users.exercise_state(session, ids[slug]) if slug in ids else None
        if state is not None and state.ladder_step_id != step_id:
            found[slug] = step_id
    return found


def _mark_today(session: Session, workout_id: int, steps: dict[str, int]) -> None:
    """Note in the saved workout's plan the level each exercise was done at for today only
    (``"today"``: its step id), so the step-down rule passes those sets over (ADR-0084)."""
    today = for_today(session, steps)
    if not today:
        return
    workout = session.get_one(Workout, workout_id)
    plan = dict(workout.planned or {})
    for slug, step_id in today.items():
        plan[slug] = {**plan.get(slug, {}), "today": step_id}
    workout.planned = plan  # a new dict, so the JSON column sees the change


def _stamp(
    session: Session, workout_id: int, items: tuple[ItemPlan, ...], sets: Sequence[Done]
) -> None:
    """Put each confirmed set's times on its rows in the saved workout (ADR-0061)."""
    ids = dict(session.execute(select(Exercise.slug, Exercise.id)).all())
    times: dict[tuple[int, int], Done] = {}
    for index, numbered in _numbered(sets):
        for number, done in numbered:
            times[(ids[items[index].slug], number)] = done
    for log in session.get_one(Workout, workout_id).sets:
        found = times.get((log.exercise_id, log.set_no))
        if found is not None:
            log.started_at, log.done_at = found.started_at, found.done_at


def save(
    session: Session,
    day: date,
    today: date,
    tz: ZoneInfo,
    answer: Resolution | None = None,
) -> workout_log.Saved | workout_log.Stale | Clash | Refused | str:
    """Save ``day``'s guided session as a workout, through the same checks as a typed log. A
    past day (one left unsaved) is saved as a past-day log (ADR-0033). A problem message when
    there is nothing to save; a clash with the day's session asks first (ADR-0060)."""
    row = _row(session, day)
    if row is None or not row.sets:
        return "no sets recorded"
    if row.after_run:
        return _save_after_run(session, row, day, today, tz)
    template = session.get_one(SessionTemplate, row.template_id)  # cascades with its progress
    # The version the sets were done in, not today's place: a switch since doesn't move them.
    block = blocks.current(session, day, tz)
    plan = session_plan(session, template.id, block, row.steps, Place(row.place))
    assert plan is not None  # noqa: S101 - the template exists
    sets = tuple(_done(s) for s in row.sets)
    # Checked again: the plan may have changed.
    if sets_problem(plan.items, sets, loaded_steps(session, plan.items, sets)) is not None:
        return "the plan changed since these sets were recorded"
    draft = workout_log.Draft(
        token=row.token,
        on=day,
        template_id=template.id,
        session_name=template.name,
        entries=entries(plan.items, sets),
        problems=(),
        strength=workout_log.strength_on(session, day, tz, template),
        backdated=day < today,
        place=plan.place,
        steps=set_levels(plan.items, sets, row.steps),
        planned=_planned(row, plan.items),
        minutes=_day_minutes(row, plan.items),
    )
    result = workout_log.save(session, draft, tz, answer)
    if isinstance(result, workout_log.Saved):
        row.saved_workout_id = result.workout_id
        if not result.already_saved:
            _stamp(session, result.workout_id, plan.items, sets)
            _mark_today(session, result.workout_id, row.steps)
    return result if result is not None else "no sets recorded"


def _save_after_run(
    session: Session, row: SessionProgress, day: date, today: date, tz: ZoneInfo
) -> workout_log.Saved | workout_log.Stale | str:
    """Add the block after a run to the day's workout (ADR-0066): the same session, so nothing
    clashes and the queue, moved by the cardio's log, doesn't move again. Only on its day."""
    if row.saved_workout_id is not None:
        return workout_log.Saved(row.saved_workout_id, already_saved=True)
    workout = _run_done(session, day)
    if day != today or workout is None or workout.template_id != row.template_id:
        return workout_log.Stale()
    template = session.get_one(SessionTemplate, row.template_id)
    block = blocks.current(session, day, tz)
    plan = session_plan(session, template.id, block, row.steps, Place(row.place))
    assert plan is not None  # noqa: S101 - the template exists
    items = _left(session, workout, plan.items)
    if items is None:
        return workout_log.Stale()
    if not items:  # the block is in the workout already: a repeated save
        return workout_log.Saved(workout.id, already_saved=True)
    sets = tuple(_done(s) for s in row.sets)
    # Checked again: the plan may have changed.
    if sets_problem(items, sets, loaded_steps(session, items, sets)) is not None:
        return "the plan changed since these sets were recorded"
    strength = workout_log.strength_on(session, day, tz, template)
    try:
        # A racing duplicate save files the same sets again: the sets' uniqueness in a workout
        # rolls it back here, so the block is never added twice.
        with session.begin_nested():
            result = workout_log.add_to(
                session,
                workout,
                entries(items, sets),
                strength,
                tz,
                set_levels(items, sets, row.steps),
                _planned(row, items),
                _day_minutes(row, items),
            )
            if isinstance(result, workout_log.Saved):
                row.saved_workout_id = result.workout_id
                _stamp(session, result.workout_id, items, sets)
                _mark_today(session, result.workout_id, row.steps)
                session.flush()
    except IntegrityError:
        session.expire_all()
        return workout_log.Saved(workout.id, already_saved=True)
    return result


NOT_TRIMMED = "this session runs as planned"
NOT_IN_SESSION = "that exercise isn't in today's session"
STARTED = "this session has started: its length stays as it is"


def choose_length(
    session: Session, plan: Guided, revision: int, minutes: int | None, pinned: Sequence[str]
) -> int | str:
    """Run today's session at ``minutes`` (None: as planned), never dropping the exercises
    ``pinned`` with Keep (ADR-0082): the new revision, or a problem. ``STALE`` when another
    device moved on since ``revision``; ``STARTED`` once a set is kept, as the length is fixed
    from then on. Nothing changes on a problem."""
    if plan.length is None:
        return NOT_TRIMMED
    if minutes is not None and minutes not in OPTIONS:
        return f"choose {', '.join(map(str, OPTIONS))} minutes, or as planned"
    if not set(pinned) <= {item.slug for item in plan.items}:
        return NOT_IN_SESSION
    row = _row(session, plan.day)
    mine = (plan.template_id, plan.place, plan.after_run)
    if row is not None and (row.template_id, row.place, row.after_run) == mine:
        if row.saved_workout_id is not None:
            return SAVED
        if row.revision != revision:
            return STALE
        if row.sets or row.fixed is not None:
            return STARTED
    else:
        # Nothing kept for this session, or a row left from another session or the other
        # place's version: start its progress as the first set would (``keep`` resets a row
        # that isn't today's), so the choice lives where a reload or another device sees it.
        started = keep(session, plan, revision, 0, [], [])
        if isinstance(started, str):
            return started
        row = _row(session, plan.day)
        assert row is not None  # noqa: S101 - started above
    row.length = {"minutes": minutes, "keep": sorted(set(pinned))}
    row.revision += 1
    session.flush()
    return row.revision


def switch(session: Session, plan: Guided, place: Place, confirm: bool) -> int | None:
    """Do ``plan``'s session at ``place`` (ADR-0071): its other version from now on, and the
    place Today starts at next time (Decided 4). Sets kept for the version shown are dropped
    with it, so with any kept the answer is their number and nothing changes until the person
    confirms (ADR-0060's ask first); None once switched. The caller checks ``plan.switch``."""
    if place is plan.place:
        return None
    row = _row(session, plan.day)
    if row is not None and row.saved_workout_id is None:
        if row.sets and not confirm:
            return len(row.sets)
        session.delete(row)  # its sets and swapped pairs belong to the other version
        session.flush()
    user_settings.update(session, place=place)
    return None


def pending(session: Session, today: date) -> list[Pending]:
    """Guided sessions from earlier days with sets but never saved: offered the next morning."""
    rows = session.scalars(
        select(SessionProgress)
        .where(SessionProgress.local_date < today, SessionProgress.saved_workout_id.is_(None))
        .order_by(SessionProgress.local_date)
    )
    out = []
    for row in rows:
        template = session.get(SessionTemplate, row.template_id)
        logged = session.scalar(  # logged another way that day (text or voice): not pending
            select(Workout.id).where(
                Workout.local_date == row.local_date, Workout.template_id == row.template_id
            )
        )
        if row.sets and template is not None and logged is None:
            out.append(Pending(row.local_date, template.name, len(row.sets)))
    return out
