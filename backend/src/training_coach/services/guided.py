"""The guided session (D1, #117): today's session for the web app, one set at a time.

Which session today is follows the same rule as a typed log (``workout_log.target``): the one
picked today, else the one at the queue's pointer; once a planned session is done or rested
today, or held for tomorrow (Rest today or Push), there is none. Sets come in work order
(ADR-0031), with any pair swapped to start with its second exercise.

The exception is a conditioning session with more than its cardio (ADR-0066): once the cardio is
logged, however it was logged, the rest of that session stays open until the day ends, and its
sets are added to the day's workout.
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

from training_coach.db.models import Exercise, SessionProgress, SessionTemplate, SetLog, Workout
from training_coach.domain.blocks import Block
from training_coach.domain.enums import ExerciseKind, Side, WorkoutStatus
from training_coach.domain.load import MAX_KG, valid_kg
from training_coach.domain.parser import LIMITS, Entry
from training_coach.domain.rest import AFTER_PAIR_SECONDS, Kind, Rest, rests
from training_coach.domain.session_times import plausible
from training_coach.domain.work_order import SetRef, work_order
from training_coach.services import blocks, workout_log
from training_coach.services.day_clash import Clash, Refused, Resolution
from training_coach.services.seed import bundled_plan
from training_coach.services.today import ItemPlan, SessionPlan, position, session_plan

WARM_UP_MINUTES = 10
SET_SECONDS = 45  # a rough working set, for the time estimate only


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
    return round(seconds / 60) + (WARM_UP_MINUTES if warm_up else 0)


def today(session: Session, on: date, tz: ZoneInfo, first: Collection[int] = ()) -> Guided | None:
    """Today's session to guide, or None when there is nothing planned left today. ``first``
    holds the pair numbers to start with their second exercise."""
    template = workout_log.target(session, on, tz)
    if template is None:
        return _after_run(session, on, tz, first)
    if held_today(session, on):
        return None
    block = blocks.current(session, on, tz)
    plan = session_plan(session, template.id, block)
    assert plan is not None  # noqa: S101 - target() returned this template a moment ago
    return _guided(on, plan, plan.items, block, first, after_run=False)


def _guided(
    on: date,
    plan: SessionPlan,
    items: tuple[ItemPlan, ...],
    block: Block | None,
    first: Collection[int],
    *,
    after_run: bool,
) -> Guided:
    groups = work_groups(items, first)
    order = _ordered(items, groups)
    warm_up = plan.kind == "strength"
    return Guided(
        day=on,
        template_id=plan.template_id,
        name=plan.name,
        focus=plan.focus,
        kind=plan.kind,
        slug=plan.slug,
        warm_up=warm_up,
        block=block,
        minutes=_minutes(items, order, warm_up),
        rest_seconds=AFTER_PAIR_SECONDS,
        items=items,
        order=order,
        after_run=after_run,
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
    plan = session_plan(session, workout.template_id, block)
    if plan is None:
        return None
    items = _left(session, workout, plan.items)
    return _guided(on, plan, items, block, first, after_run=True) if items else None


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
    (ADR-0061), both or neither. ``load_kg``: the weight, on a loaded step only (ADR-0072)."""

    item: int
    set_no: int
    left: int
    right: int | None = None
    started_at: datetime | None = None
    done_at: datetime | None = None
    load_kg: float | None = None


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


@dataclass(frozen=True)
class Pending:
    day: date
    session: str
    sets: int


def _row(session: Session, day: date) -> SessionProgress | None:
    return session.scalar(select(SessionProgress).where(SessionProgress.local_date == day))


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
    )


def kept(session: Session, day: date) -> Kept | None:
    """The progress kept for ``day``, if any."""
    row = _row(session, day)
    return _kept(row) if row is not None else None


def sets_problem(items: tuple[ItemPlan, ...], sets: Sequence[Done]) -> str | None:
    """What's wrong with ``sets`` against the plan's items, or None: each set is one the plan
    has, recorded once, with values in range and sides only where the exercise has them."""
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
        if done.load_kg is not None and item.load is None:
            return f"{item.exercise} isn't done with a weight"
        if done.load_kg is not None and not valid_kg(done.load_kg):
            return f"{item.exercise}: a weight is more than 0 and at most {MAX_KG:g} kg"
    return None


def _problem(plan: Guided, position: int, first: Sequence[int], sets: Sequence[Done]) -> str | None:
    if not 0 <= position <= len(plan.order):
        return "position out of range"
    pairs = {item.pair for item in plan.items if item.pair is not None}
    if any(number not in pairs for number in first):
        return "no such pair"
    return sets_problem(plan.items, sets)


STALE = "this session changed on another device; reload it"


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
    plausible at ``now`` (default: the clock's now; ADR-0061)."""
    problem = _problem(plan, position, first, sets)
    if problem is not None:
        return problem
    row = _row(session, plan.day)
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
        return "this session is saved already"
    if row is not None and row.template_id != plan.template_id:
        if revision != 0:  # this browser still shows the old session: nothing is deleted
            return STALE
        session.delete(row)  # the day's session changed (a pick or swap): start afresh
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
                )
                session.add(row)
            row.revision += 1
            row.position = position
            row.first = sorted(set(first))
            at = now or datetime.now(UTC)
            row.sets = [_stored(_timed(done, at)) for done in sets]
            session.flush()
    except IntegrityError:
        return STALE
    return row.revision


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
    plan = session_plan(session, template.id, blocks.current(session, day, tz))
    assert plan is not None  # noqa: S101 - the template exists
    sets = tuple(_done(s) for s in row.sets)
    if sets_problem(plan.items, sets) is not None:  # checked again: the plan may have changed
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
    )
    result = workout_log.save(session, draft, tz, answer)
    if isinstance(result, workout_log.Saved):
        row.saved_workout_id = result.workout_id
        if not result.already_saved:
            _stamp(session, result.workout_id, plan.items, sets)
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
    plan = session_plan(session, template.id, blocks.current(session, day, tz))
    assert plan is not None  # noqa: S101 - the template exists
    items = _left(session, workout, plan.items)
    if items is None:
        return workout_log.Stale()
    if not items:  # the block is in the workout already: a repeated save
        return workout_log.Saved(workout.id, already_saved=True)
    sets = tuple(_done(s) for s in row.sets)
    if sets_problem(items, sets) is not None:  # checked again: the plan may have changed
        return "the plan changed since these sets were recorded"
    strength = workout_log.strength_on(session, day, tz, template)
    try:
        # A racing duplicate save files the same sets again: the sets' uniqueness in a workout
        # rolls it back here, so the block is never added twice.
        with session.begin_nested():
            result = workout_log.add_to(session, workout, entries(items, sets), strength, tz)
            if isinstance(result, workout_log.Saved):
                row.saved_workout_id = result.workout_id
                _stamp(session, result.workout_id, items, sets)
                session.flush()
    except IntegrityError:
        session.expire_all()
        return workout_log.Saved(workout.id, already_saved=True)
    return result


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
