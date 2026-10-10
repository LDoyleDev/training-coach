"""The guided session (D1, #117): today's session for the web app, one set at a time.

Which session today is follows the same rule as a typed log (``workout_log.target``): the one
picked today, else the one at the queue's pointer; once a planned session is done or rested
today there is none. Sets come in work order (ADR-0031), with any pair swapped to start with
its second exercise.
"""

import secrets
from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from training_coach.db.models import SessionProgress, SessionTemplate, Workout
from training_coach.domain.blocks import Block
from training_coach.domain.enums import ExerciseKind, Side
from training_coach.domain.parser import LIMITS, Entry
from training_coach.domain.work_order import work_order
from training_coach.services import blocks, workout_log
from training_coach.services.today import ItemPlan, session_plan

REST_SECONDS = 60  # after each set, adjustable during the rest (D1)
WARM_UP_MINUTES = 10
SET_SECONDS = 45  # a rough working set, for the time estimate only


@dataclass(frozen=True)
class GuidedSet:
    item: int  # index into items
    set_no: int  # from 1
    target: int


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
    rest_seconds: int
    items: tuple[ItemPlan, ...]
    order: tuple[GuidedSet, ...]
    slug: str = ""  # the session template's


def _minutes(items: tuple[ItemPlan, ...], warm_up: bool) -> int:
    seconds = 0
    for item in items:
        sides = 2 if item.per_side else 1
        for target in item.targets:
            if item.kind is ExerciseKind.DURATION_MIN:
                seconds += target * 60
            elif item.kind is ExerciseKind.SECONDS:
                seconds += target * sides + REST_SECONDS
            else:
                seconds += SET_SECONDS * sides + REST_SECONDS
    return round(seconds / 60) + (WARM_UP_MINUTES if warm_up else 0)


def today(session: Session, on: date, tz: ZoneInfo, first: Collection[int] = ()) -> Guided | None:
    """Today's session to guide, or None when there is nothing planned left today. ``first``
    holds the pair numbers to start with their second exercise."""
    template = workout_log.target(session, on, tz)
    if template is None:
        return None
    block = blocks.current(session, on, tz)
    plan = session_plan(session, template.id, block)
    assert plan is not None  # noqa: S101 - target() returned this template a moment ago
    groups = work_order([len(i.targets) for i in plan.items], [i.pair for i in plan.items], first)
    order = tuple(
        GuidedSet(item, set_no, plan.items[item].targets[set_no - 1])
        for group in groups
        for item, set_no in group
    )
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
        minutes=_minutes(plan.items, warm_up),
        rest_seconds=REST_SECONDS,
        items=plan.items,
        order=order,
    )


# ---------------------------------------------------------------- progress and saving


@dataclass(frozen=True)
class Done:
    """A confirmed set: ``right`` only for one-sided exercises (None means the same as left)."""

    item: int
    set_no: int
    left: int
    right: int | None = None


@dataclass(frozen=True)
class Kept:
    day: date
    template_id: int
    position: int
    first: tuple[int, ...]
    sets: tuple[Done, ...]
    saved: bool
    revision: int = 0


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
        sets=tuple(Done(**s) for s in row.sets),
        saved=row.saved_workout_id is not None,
        revision=row.revision,
    )


def kept(session: Session, day: date) -> Kept | None:
    """The progress kept for ``day``, if any."""
    row = _row(session, day)
    return _kept(row) if row is not None else None


def _sets_problem(items: tuple[ItemPlan, ...], sets: Sequence[Done]) -> str | None:
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
    return None


def _problem(plan: Guided, position: int, first: Sequence[int], sets: Sequence[Done]) -> str | None:
    if not 0 <= position <= len(plan.order):
        return "position out of range"
    pairs = {item.pair for item in plan.items if item.pair is not None}
    if any(number not in pairs for number in first):
        return "no such pair"
    return _sets_problem(plan.items, sets)


STALE = "this session changed on another device; reload it"


def keep(
    session: Session,
    plan: Guided,
    revision: int,
    position: int,
    first: Sequence[int],
    sets: Sequence[Done],
) -> int | str:
    """Keep where the person is in today's guided session: the new revision, or a problem.

    Every value is checked against the plan: nothing from the browser is trusted. The browser
    names the ``revision`` it last saw (0 before any); if the kept one is newer (another device
    moved on), nothing is written and ``STALE`` is returned."""
    problem = _problem(plan, position, first, sets)
    if problem is not None:
        return problem
    row = _row(session, plan.day)
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
                )
                session.add(row)
            row.revision += 1
            row.position = position
            row.first = sorted(set(first))
            row.sets = [vars(done) for done in sets]
            session.flush()
    except IntegrityError:
        return STALE
    return row.revision


def _entries(items: tuple[ItemPlan, ...], sets: Sequence[Done]) -> tuple[Entry, ...]:
    """The confirmed sets as log entries, per exercise in set order and numbered from 1. A
    skipped set isn't logged, so sets 1 and 3 done become sets 1 and 2 of the log."""
    by_item: dict[int, list[Done]] = {}
    for done in sorted(sets, key=lambda d: (d.item, d.set_no)):
        by_item.setdefault(done.item, []).append(done)
    entries = []
    for index, dones in by_item.items():
        item = items[index]
        rows: list[tuple[int, Side, int]] = []
        for number, done in enumerate(dones, start=1):
            if item.per_side:
                right = done.left if done.right is None else done.right
                rows += [(number, Side.LEFT, done.left), (number, Side.RIGHT, right)]
            else:
                rows.append((number, Side.BOTH, done.left))
        entries.append(Entry(item.slug, tuple(rows)))
    return tuple(entries)


def save(
    session: Session, day: date, today: date, tz: ZoneInfo
) -> workout_log.Saved | workout_log.Stale | str:
    """Save ``day``'s guided session as a workout, through the same checks as a typed log. A
    past day (one left unsaved) is saved as a past-day log (ADR-0033). A problem message when
    there is nothing to save."""
    row = _row(session, day)
    if row is None or not row.sets:
        return "no sets recorded"
    template = session.get_one(SessionTemplate, row.template_id)  # cascades with its progress
    plan = session_plan(session, template.id, blocks.current(session, day, tz))
    assert plan is not None  # noqa: S101 - the template exists
    sets = tuple(Done(**s) for s in row.sets)
    if _sets_problem(plan.items, sets) is not None:  # checked again: the plan may have changed
        return "the plan changed since these sets were recorded"
    draft = workout_log.Draft(
        token=row.token,
        on=day,
        template_id=template.id,
        session_name=template.name,
        entries=_entries(plan.items, sets),
        problems=(),
        strength=workout_log.strength_on(session, day, tz, template),
        backdated=day < today,
    )
    result = workout_log.save(session, draft, tz)
    if isinstance(result, workout_log.Saved):
        row.saved_workout_id = result.workout_id
    return result if result is not None else "no sets recorded"


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
