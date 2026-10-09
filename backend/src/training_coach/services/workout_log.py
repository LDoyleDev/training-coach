"""Turning typed logs into saved workouts (step 1-E; ADR-0006, ADR-0014, ADR-0016, ADR-0022).

The bot parses a message into a ``Draft``, shows it, and calls ``save`` only after "Save".
Every draft carries a random token stored on the workout, so saving the same draft twice
(a double tap, a duplicate Telegram callback) returns the first workout and changes nothing.
The caller owns the transaction.
"""

import re
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import (
    Event,
    Exercise,
    SessionTemplate,
    SetLog,
    TemplateItem,
    Workout,
)
from training_coach.domain.blocks import BlockKind
from training_coach.domain.dates import DateLine, date_line
from training_coach.domain.enums import ExerciseKind, WorkoutStatus
from training_coach.domain.parser import Entry, Known, ParseResult, normalise_name, parse_log
from training_coach.domain.queue import ADVANCING, Position, caught_up, complete
from training_coach.services import blocks, users
from training_coach.services.groq import Rewrite
from training_coach.services.today import position

EXTRA = "Extra session"
REST_WORD = re.compile(r"\brest\b", re.IGNORECASE)
REST_HAS_SETS = "A rest day has no sets: send the rest day and the sets separately."


@dataclass(frozen=True)
class Draft:
    """What the user is asked to confirm. ``template_id`` None means an extra session."""

    token: str
    on: date  # the day it was drafted for; saving after midnight keeps it
    template_id: int | None
    session_name: str  # "Upper" or "Extra session"
    entries: tuple[Entry, ...]
    problems: tuple[str, ...]
    # Whether the strength prescription applied when drafted (ADR-0028). If it no longer does
    # at save time (blocks turned on or off meanwhile), the draft is stale: saving it would
    # file the sets at the wrong step and in the wrong block's history.
    strength: bool = False
    backdated: bool = False  # a past day logged late (#104): no target check, own queue rule
    rest: bool = False  # a past rest day: no sets


@dataclass(frozen=True)
class Saved:
    workout_id: int
    already_saved: bool  # True when this draft had been saved before: nothing changed


@dataclass(frozen=True)
class Stale:
    """The draft no longer fits: today's target session changed (rest, swap, pick or another
    log) or it names an exercise that is gone. Nothing was written; ask for the log again."""


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
        .where(
            Event.kind == "queue.picked",
            Event.at >= _day_start_utc(on, tz),
            Event.at < _day_start_utc(on + timedelta(days=1), tz),
        )
        .order_by(Event.id.desc())
        .limit(1)
    )
    picked_id = picked.get("picked") if isinstance(picked, dict) else None
    if isinstance(picked_id, int):
        template = session.get(SessionTemplate, picked_id)
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

    def one_sided(exercise: Exercise) -> bool:
        # A retired exercise is in no session: its own flag says (#107).
        return in_target.get(exercise.id, anywhere.get(exercise.id, exercise.per_side))

    return [
        Known(e.slug, (e.name, *e.aliases), ExerciseKind(e.kind), one_sided(e))
        for e in session.scalars(select(Exercise).order_by(Exercise.id))
    ]


def exercise_names(session: Session) -> list[str]:
    """Every exercise's display name, in plan order: Whisper's vocabulary and the model's enum."""
    return list(session.scalars(select(Exercise.name).order_by(Exercise.id)))


def exercise_labels(session: Session) -> dict[str, tuple[str, ExerciseKind]]:
    """Display name and kind by slug, for showing a draft back to the user."""
    return {e.slug: (e.name, ExerciseKind(e.kind)) for e in session.scalars(select(Exercise))}


def next_session_name(session: Session) -> str | None:
    """The session the queue points at now, e.g. after a save moved it on."""
    current = position(session)
    upcoming = session.get(SessionTemplate, current.pointer) if current is not None else None
    return upcoming.name if upcoming is not None else None


def _strength(session: Session, on: date, tz: ZoneInfo, template: SessionTemplate | None) -> bool:
    """Whether a log on ``on`` for ``template`` is trained under the strength prescription."""
    block = blocks.current(session, on, tz)
    return blocks.strength_applies(block, template.kind if template is not None else None)


def draft(session: Session, text: str, on: date, tz: ZoneInfo) -> Draft:
    """Parse a message into something to confirm. Never writes.

    A date on the first line (``domain.dates``) makes it a log for that past day (#104)."""
    first, _, body = text.partition("\n")
    dated = date_line(first, on)
    if isinstance(dated, str):
        return Draft(secrets.token_hex(16), on, None, EXTRA, (), (dated,))
    if dated is not None and dated.day < on:
        return _draft_past(session, dated, body, tz)
    if dated is not None:  # today's date on top: an ordinary log
        text = body
    template = target(session, on, tz)
    parsed: ParseResult = parse_log(text, catalogue(session, template))
    return Draft(
        token=secrets.token_hex(16),
        on=on,
        template_id=template.id if template is not None else None,
        session_name=template.name if template is not None else EXTRA,
        entries=parsed.entries,
        problems=parsed.problems,
        strength=_strength(session, on, tz, template),
    )


def _named(session: Session, words: str) -> SessionTemplate | None:
    """The planned session the date line names ("Legs", "Day 3 Torso + neck"), if any: the
    longest session name or slug found among its words."""
    wanted = f" {normalise_name(words)} "
    best: tuple[int, SessionTemplate] | None = None
    for template in session.scalars(select(SessionTemplate).order_by(SessionTemplate.position)):
        for name in (template.name, template.slug.replace("-", " ")):
            normal = normalise_name(name)
            if normal and f" {normal} " in wanted and (best is None or len(normal) > best[0]):
                best = (len(normal), template)
    return best[1] if best is not None else None


def _inferred(session: Session, entries: tuple[Entry, ...]) -> SessionTemplate | None:
    """The planned session sharing the most exercises with a log; ties go to the earlier one."""
    logged = {entry.slug for entry in entries}
    best: tuple[int, SessionTemplate] | None = None
    templates = session.scalars(
        select(SessionTemplate)
        .order_by(SessionTemplate.position)
        .options(selectinload(SessionTemplate.items).selectinload(TemplateItem.exercise))
    )
    for template in templates:
        shared = len(logged & {item.exercise.slug for item in template.items})
        if shared and (best is None or shared > best[0]):
            best = (shared, template)
    return best[1] if best is not None else None


def _draft_past(session: Session, dated: DateLine, body: str, tz: ZoneInfo) -> Draft:
    rest = REST_WORD.search(dated.rest) is not None
    template = _named(session, dated.rest)
    if rest:
        entries: tuple[Entry, ...] = ()
        problems: tuple[str, ...] = (REST_HAS_SETS,) if body.strip() else ()
    else:
        parsed = parse_log(body, catalogue(session, template))
        if template is None:  # name it from the exercises, then read again for its sides
            template = _inferred(session, parsed.entries)
            parsed = parse_log(body, catalogue(session, template)) if template else parsed
        entries, problems = parsed.entries, parsed.problems
    return Draft(
        token=secrets.token_hex(16),
        on=dated.day,
        template_id=template.id if template is not None else None,
        session_name=template.name if template is not None else EXTRA,
        entries=entries,
        problems=problems,
        strength=_strength(session, dated.day, tz, template),
        backdated=True,
        rest=rest,
    )


def _saved_before(session: Session, token: str) -> Saved | None:
    existing = session.scalar(select(Workout.id).where(Workout.log_token == token))
    return Saved(existing, already_saved=True) if existing is not None else None


def rewrite_text(rewrite: Rewrite) -> str:
    """The model's reading as plain log text, so the rule parser judges it like anything
    typed: names must match exactly, values are bounded, units must fit (ADR-0007)."""
    return "\n".join(
        f"{line.exercise} " + " ".join(f"{value}{line.unit}" for value in line.sets)
        for line in rewrite.lines
        if line.sets
    )


def _exercises(session: Session, confirmed: Draft) -> dict[str, Exercise] | None:
    """The draft's exercises by slug, or None if any of them is gone from the plan."""
    slugs = {x.slug for x in confirmed.entries}
    found = {e.slug: e for e in session.scalars(select(Exercise).where(Exercise.slug.in_(slugs)))}
    return found if len(found) == len(slugs) else None


def _file(
    session: Session,
    workout: Workout,
    confirmed: Draft,
    exercises: dict[str, Exercise],
    strength: bool,
    tz: ZoneInfo,
) -> None:
    """The workout's block (ADR-0028) and its sets at the current ladder steps."""
    block = blocks.current(session, confirmed.on, tz)
    if strength:
        workout.block = BlockKind.STRENGTH
    elif block is not None and block.kind is BlockKind.HYPERTROPHY:
        workout.block = BlockKind.HYPERTROPHY
    for entry in confirmed.entries:
        exercise = exercises[entry.slug]
        step_id = blocks.step_for(session, exercise, strength)[0].id
        workout.sets.extend(
            SetLog(exercise_id=exercise.id, ladder_step_id=step_id, set_no=n, side=side, value=v)
            for n, side, v in entry.sets
        )


def _commit(session: Session, workout: Workout, confirmed: Draft, moved: Position | None) -> Saved:
    """Add the workout and the queue move in one savepoint, then log the event."""
    plan = users.plan_state(session)
    try:
        # A racing duplicate save (same token) rolls both back together, so the queue can
        # never move twice.
        with session.begin_nested():
            session.add(workout)
            if plan is not None and moved is not None:
                plan.next_template_id = moved.pointer
                plan.queued = list(moved.queued)
            session.flush()
    except IntegrityError:
        session.expire_all()
        before = _saved_before(session, confirmed.token)
        if before is None:
            raise
        return before
    session.add(
        Event(
            kind="workout.logged",
            payload={
                "workout_id": workout.id,
                "template_id": confirmed.template_id,
                "exercises": len(confirmed.entries),
                "sets": len(workout.sets),
                **({"day": confirmed.on.isoformat()} if confirmed.backdated else {}),
            },
        )
    )
    return Saved(workout.id, already_saved=False)


def _order(session: Session) -> list[int]:
    return list(session.scalars(select(SessionTemplate.id).order_by(SessionTemplate.position)))


def save(session: Session, confirmed: Draft, tz: ZoneInfo) -> Saved | Stale | None:
    """Write the workout, its sets at the current ladder steps and the queue move.

    Nothing in the draft is trusted beyond what is re-checked here: a draft saved before
    returns that workout with ``already_saved``; one whose target session or exercises no
    longer fit returns ``Stale``; one with no entries returns None. None of them write.
    """
    if (before := _saved_before(session, confirmed.token)) is not None:
        return before
    if confirmed.backdated:
        return _save_past(session, confirmed, tz)
    if not confirmed.entries:
        return None
    now = target(session, confirmed.on, tz)
    if (now.id if now is not None else None) != confirmed.template_id:
        return Stale()
    exercises = _exercises(session, confirmed)
    if exercises is None:
        return Stale()
    # ADR-0028: a planned strength session in a strength block is trained, and filed, under the
    # strength prescription (one step harder); everything else is ordinary history.
    strength = _strength(session, confirmed.on, tz, now)
    if strength != confirmed.strength:
        return Stale()
    workout = Workout(
        local_date=confirmed.on,
        template_id=confirmed.template_id,
        status=WorkoutStatus.DONE,  # only done workouts carry sets (rest/skip have none)
        log_token=confirmed.token,
    )
    _file(session, workout, confirmed, exercises, strength, tz)
    current = position(session)
    moved = (
        complete(_order(session), current, confirmed.template_id, WorkoutStatus.DONE)
        if current is not None
        else None
    )
    return _commit(session, workout, confirmed, moved)


def _save_past(session: Session, confirmed: Draft, tz: ZoneInfo) -> Saved | Stale | None:
    """A past day logged late (#104, ADR-0033): filed under that day; the queue moves to the
    session after it only when it's a planned session and nothing later is logged."""
    if (not confirmed.entries and not confirmed.rest) or (confirmed.rest and confirmed.problems):
        return None
    template = (
        session.get(SessionTemplate, confirmed.template_id)
        if confirmed.template_id is not None
        else None
    )
    exercises = _exercises(session, confirmed)
    if (confirmed.template_id is not None and template is None) or exercises is None:
        return Stale()
    strength = _strength(session, confirmed.on, tz, template)
    if strength != confirmed.strength:
        return Stale()
    workout = Workout(
        local_date=confirmed.on,
        template_id=confirmed.template_id,
        status=WorkoutStatus.REST if confirmed.rest else WorkoutStatus.DONE,
        log_token=confirmed.token,
    )
    _file(session, workout, confirmed, exercises, strength, tz)
    later = session.scalar(select(Workout.id).where(Workout.local_date > confirmed.on).limit(1))
    moved = caught_up(_order(session), template.id) if template and later is None else None
    return _commit(session, workout, confirmed, moved)


def strength_on(session: Session, on: date, tz: ZoneInfo, template: SessionTemplate | None) -> bool:
    """Whether a log on ``on`` for ``template`` is filed under the strength prescription
    (ADR-0028): what a draft must carry, for drafts built elsewhere (the guided session)."""
    return _strength(session, on, tz, template)
