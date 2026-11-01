"""Turning typed logs into saved workouts (step 1-E; ADR-0006, ADR-0014, ADR-0016, ADR-0022).

The bot parses a message into a ``Draft``, shows it, and calls ``save`` only after "Save".
Every draft carries a random token stored on the workout, so saving the same draft twice
(a double tap, a duplicate Telegram callback) returns the first workout and changes nothing.
The caller owns the transaction.
"""

import re
import secrets
from collections.abc import Callable
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
from training_coach.domain.cardio import NO_DETAILS, TIMED, Details, activity_in
from training_coach.domain.dates import DateLine, date_line
from training_coach.domain.enums import ExerciseKind, Place, WorkoutStatus
from training_coach.domain.parser import Entry, Known, ParseResult, normalise_name, parse_log
from training_coach.domain.places import day_place
from training_coach.domain.queue import (
    ADVANCING,
    Position,
    caught_up,
    complete,
    local_date,
    resettled,
)
from training_coach.services import blocks, day_clash, undo, user_settings, users
from training_coach.services.blocks import load_kit, loadable
from training_coach.services.day_clash import Clash, Refused, Resolution, Resolved
from training_coach.services.groq import Rewrite
from training_coach.services.today import away_on, position

EXTRA = "Extra session"
REST_WORD = re.compile(r"\brest\b", re.IGNORECASE)
TODAY_WORD = re.compile(r"^\s*today\b", re.IGNORECASE)
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
    # Logged as an extra on purpose, whatever is planned today (the web's Log activity when
    # today's session is a different one): never completes it, never moves the queue.
    extra: bool = False
    activity: str | None = None  # CardioActivity, for a cardio log
    # Where it was done (ADR-0071); empty: the day's place, as the session plan has it.
    place: Place | None = None
    cardio: Details = NO_DETAILS  # effort, distance, heart rate, start (ADR-0067)
    # Today's log of a session named on purpose ("today Arms", or picked on the web), whatever
    # the queue offers (ADR-0060): done out of turn, it leaves the queue where it is (ADR-0016).
    chosen: bool = False
    # (slug, set number, ladder step id): a set done at a level changed in the guided session
    # (ADR-0080), filed at that step instead of the current one. A step not on the exercise's
    # ladder is ignored.
    steps: tuple[tuple[str, int, int], ...] = ()
    # A guided session's plan (ADR-0084): (slug, sets planned) per exercise, and the minutes
    # chosen for the day (ADR-0082), None as planned. A typed log plans nothing (None).
    planned: tuple[tuple[str, int], ...] | None = None
    minutes: int | None = None


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

    def loaded(exercise: Exercise) -> bool:
        # A typed weight goes with the step the person trains, when it takes load (ADR-0072).
        if not loadable(exercise.slug):
            return False
        return (
            load_kit(exercise.slug, blocks.step_for(session, exercise, False)[0].name) is not None
        )

    return [
        Known(e.slug, (e.name, *e.aliases), ExerciseKind(e.kind), one_sided(e), loaded(e))
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

    A date on the first line (``domain.dates``) makes it a log for that past day (#104). A
    session named on the first line, alone or after ``today``, makes it today's log of that
    session, whatever the queue offers (ADR-0060)."""
    first, _, body = text.partition("\n")
    dated = date_line(first, on)
    if isinstance(dated, str):
        return Draft(secrets.token_hex(16), on, None, EXTRA, (), (dated,))
    if dated is not None and dated.day < on:
        return _draft_past(session, dated, body, tz)
    named = _named(session, dated.rest) if dated is not None else _session_line(session, first)
    if _today_words(first, dated, named):  # "today, rest of the legs": the words are the log's
        text = f"{dated.rest}\n{body}" if dated is not None else text
    elif dated is not None or named is not None:  # today's date or a session on top
        text = body
    if named is not None:
        return _draft_named(session, named, text, on, tz)
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
        activity=_activity(text, parsed.entries),
    )


def _activity(text: str, entries: tuple[Entry, ...]) -> str | None:
    """A walk, ride or run named in a log of one timed cardio exercise (ux-flow-plan A1)."""
    if len(entries) != 1 or entries[0].slug not in TIMED:
        return None
    found = activity_in(text)
    return found.value if found is not None else None


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


def _session_line(session: Session, line: str) -> SessionTemplate | None:
    """The session a first line is just the name of, after an optional ``today`` ("Arms",
    "today Zone 2"), if any. Only the whole line counts: "Legs 3x10" is a log."""
    wanted = normalise_name(TODAY_WORD.sub("", line))
    if not wanted:
        return None
    for template in session.scalars(select(SessionTemplate).order_by(SessionTemplate.position)):
        if wanted in (normalise_name(template.name), normalise_name(template.slug)):
            return template
    return None


def _today_words(first: str, dated: DateLine | None, named: SessionTemplate | None) -> bool:
    """``today`` followed by words that name no session ("today, rest of the legs"): not a
    heading, as ``today`` starts sentences far more often than a date does (review of #242)."""
    return (
        dated is not None
        and named is None
        and bool(dated.rest)
        and TODAY_WORD.match(first) is not None
    )


def heading(session: Session, line: str, on: date) -> bool:
    """Whether a log's first line is a date or a session's name: the model then reads only the
    lines under it, and its reading goes back under the same line (#104, ADR-0060)."""
    dated = date_line(line, on)
    named = _session_line(session, line)
    if isinstance(dated, DateLine) and named is None:
        named = _named(session, dated.rest)
        if _today_words(line, dated, named):
            return False
    return dated is not None or named is not None


def _draft_named(
    session: Session, template: SessionTemplate, body: str, on: date, tz: ZoneInfo
) -> Draft:
    """Today's log of a session named on purpose: done out of turn unless the queue is on it."""
    parsed = parse_log(body, catalogue(session, template))
    return Draft(
        token=secrets.token_hex(16),
        on=on,
        template_id=template.id,
        session_name=template.name,
        entries=parsed.entries,
        problems=parsed.problems,
        strength=_strength(session, on, tz, template),
        activity=_activity(body, parsed.entries),
        chosen=True,
    )


def _inferred(session: Session, entries: tuple[Entry, ...]) -> SessionTemplate | None:
    """The planned session sharing the most exercises with a log; ties go to the earlier one."""
    logged = {entry.slug for entry in entries}
    best: tuple[int, SessionTemplate] | None = None
    templates = session.scalars(
        select(SessionTemplate)
        .order_by(SessionTemplate.position)
        .options(
            selectinload(SessionTemplate.items).selectinload(TemplateItem.exercise),
            selectinload(SessionTemplate.gym_items).selectinload(TemplateItem.exercise),
        )
    )
    for template in templates:
        # Either version: a log of gym exercises is that session at the gym (ADR-0071).
        items = (*template.items, *template.gym_items)
        shared = len(logged & {item.exercise.slug for item in items})
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
        activity=_activity(body, entries),
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
        # The home kit locks nothing at a gym (ADR-0071); away, no kit at all (ADR-0086).
        at_gym, away = workout.place == Place.GYM, workout.place == Place.AWAY
        step = blocks.step_for(session, exercise, strength, at_gym=at_gym, away=away)[0]
        if away:  # a step that needs none, for the day
            step = blocks.kit_free(session, exercise, step)
        step_id = step.id
        done_at = {n: step for slug, n, step in confirmed.steps if slug == entry.slug}
        if done_at:  # only steps of the exercise's own ladder
            own = {s.id for s in exercise.ladder}
            done_at = {n: step for n, step in done_at.items() if step in own}
        kg = dict(entry.loads)
        workout.sets.extend(
            SetLog(
                exercise_id=exercise.id,
                ladder_step_id=done_at.get(n, step_id),
                set_no=n,
                side=side,
                value=v,
                load_kg=kg.get(n),
            )
            for n, side, v in entry.sets
        )


Saving = Saved | Stale | Clash | Refused | None


def _commit(
    session: Session,
    workout: Workout,
    confirmed: Draft,
    rule: Callable[[], Position | None],
    answer: Resolution | None,
    tz: ZoneInfo,
) -> Saved | Clash | Refused:
    """Add the workout and the queue move in one savepoint, then log the event.

    A planned session or rest day for a day that already has one is a clash (ADR-0060):
    nothing is written until ``answer`` says what to do with what is there. A replace or a
    move settles the queue by ADR-0033's catching-up rule; otherwise ``rule`` moves it."""
    day_clash.sweep(session, datetime.now(UTC))  # every save, not only a replace
    plan = users.plan_state(session)
    queue_before = undo.snapshot(session)
    resolved: Resolved | None = None
    try:
        # A racing duplicate save (same token) rolls both back together, so the queue can
        # never move twice.
        with session.begin_nested():
            clash = (
                day_clash.recorded(session, confirmed.on)
                if day_clash.can_clash(confirmed.template_id, confirmed.rest)
                else None
            )
            latest = day_clash.latest_done(session)
            if clash is not None:
                if answer is None:
                    return clash
                found = day_clash.resolve(session, clash, answer, local_date(datetime.now(UTC), tz))
                if not isinstance(found, Resolved):
                    return found  # nothing was written
                resolved = found
            session.add(workout)
            session.flush()
            if resolved is not None and resolved.action != day_clash.ADD:
                current = position(session)
                moved = (
                    resettled(_order(session), current, latest, day_clash.latest_done(session))
                    if current is not None
                    else None
                )
            else:
                moved = rule()
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
    record = undo.record(queue_before, undo.snapshot(session), workout)
    session.add(
        Event(
            kind="workout.logged",
            payload={
                "workout_id": workout.id,
                "template_id": confirmed.template_id,
                "exercises": len(confirmed.entries),
                "sets": len(workout.sets),
                **({"day": confirmed.on.isoformat()} if confirmed.backdated else {}),
                **({"resolved": resolved.action} if resolved is not None else {}),
                "undo": {**record, **(resolved.undo() if resolved is not None else {})},
            },
        )
    )
    return Saved(workout.id, already_saved=False)


def _place(session: Session, confirmed: Draft) -> Place:
    """Where a log was done: the draft's place, else the day's (ADR-0071; away when the day was
    chosen as away, ADR-0086), and for a planned session the place of the version done there:
    home when it has no version for that place."""
    if confirmed.place is not None:
        at = confirmed.place
    elif away_on(session, confirmed.on):
        at = Place.AWAY
    else:
        prefs = user_settings.load(session)
        at = day_place(prefs.places, prefs.place)
    template = (
        session.get(SessionTemplate, confirmed.template_id)
        if confirmed.template_id is not None
        else None
    )
    return template.done_at(at) if template is not None else at


def _order(session: Session) -> list[int]:
    return list(session.scalars(select(SessionTemplate.id).order_by(SessionTemplate.position)))


def save(
    session: Session, confirmed: Draft, tz: ZoneInfo, answer: Resolution | None = None
) -> Saving:
    """Write the workout, its sets at the current ladder steps and the queue move.

    Nothing in the draft is trusted beyond what is re-checked here: a draft saved before
    returns that workout with ``already_saved``; one whose target session or exercises no
    longer fit returns ``Stale``; one with no entries returns None; one for a day that already
    has its session returns the ``Clash`` to ask about, until ``answer`` resolves it (or
    ``Refused`` when the answer can't be carried out). None of those write.
    """
    if (before := _saved_before(session, confirmed.token)) is not None:
        return before
    if confirmed.backdated:
        return _save_past(session, confirmed, tz, answer)
    if not confirmed.entries:
        return None
    if confirmed.chosen:
        now = (
            session.get(SessionTemplate, confirmed.template_id)
            if confirmed.template_id is not None
            else None
        )
        if now is None:
            return Stale()
    else:
        now = None if confirmed.extra else target(session, confirmed.on, tz)
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
        activity=confirmed.activity,
        place=_place(session, confirmed),
        minutes=confirmed.minutes,
        planned=plan_map(confirmed.planned),
        **_details(confirmed.cardio),
    )
    _file(session, workout, confirmed, exercises, strength, tz)

    def rule() -> Position | None:
        # At the pointer it moves on; a session chosen out of turn leaves it (ADR-0016).
        current = position(session)
        if current is None:
            return None
        return complete(_order(session), current, confirmed.template_id, WorkoutStatus.DONE)

    return _commit(session, workout, confirmed, rule, answer, tz)


def add_to(
    session: Session,
    workout: Workout,
    entries: tuple[Entry, ...],
    strength: bool,
    tz: ZoneInfo,
    steps: tuple[tuple[str, int, int], ...] = (),
    planned: tuple[tuple[str, int], ...] | None = None,
    minutes: int | None = None,
) -> Saved | Stale:
    """Add sets to a saved workout of the same session: the block after a conditioning
    session's cardio (ADR-0066). It is that session's log, so it neither clashes nor moves the
    queue. ``Stale`` when an exercise is gone from the plan. ``planned`` joins the workout's
    plan (ADR-0084); an exercise the plan doesn't name had every set planned. ``minutes``: the
    block ran shorter for the day (ADR-0082); None leaves the workout's own minutes as they are."""
    confirmed = Draft(
        token=workout.log_token or secrets.token_hex(16),
        on=workout.local_date,
        template_id=workout.template_id,
        session_name="",
        entries=entries,
        problems=(),
        strength=strength,
        steps=steps,
    )
    exercises = _exercises(session, confirmed)
    if exercises is None:
        return Stale()
    _file(session, workout, confirmed, exercises, strength, tz)
    added = plan_map(planned)
    if added is not None:
        workout.planned = {**(workout.planned or {}), **added}
    if minutes is not None:
        workout.minutes = minutes
    session.flush()
    session.add(
        Event(
            kind="workout.added",
            payload={
                "workout_id": workout.id,
                "exercises": len(entries),
                "sets": len(workout.sets),
            },
        )
    )
    return Saved(workout.id, already_saved=False)


def _save_past(
    session: Session, confirmed: Draft, tz: ZoneInfo, answer: Resolution | None
) -> Saving:
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
        activity=confirmed.activity,
        place=_place(session, confirmed),
        minutes=confirmed.minutes,
        planned=plan_map(confirmed.planned),
        **_details(confirmed.cardio),
    )
    _file(session, workout, confirmed, exercises, strength, tz)

    def rule() -> Position | None:
        later = session.scalar(select(Workout.id).where(Workout.local_date > confirmed.on).limit(1))
        return caught_up(_order(session), template.id) if template and later is None else None

    return _commit(session, workout, confirmed, rule, answer, tz)


def plan_map(planned: tuple[tuple[str, int], ...] | None) -> dict[str, dict[str, int]] | None:
    """A guided session's plan as ``workouts.planned`` keeps it (ADR-0084): exercise slug ->
    {"sets": N}, room left for a later key per exercise. None for a log without a plan."""
    if planned is None:
        return None
    found: dict[str, dict[str, int]] = {}
    for slug, sets in planned:  # an exercise twice in a session plans the sets of both
        found[slug] = {"sets": found.get(slug, {"sets": 0})["sets"] + sets}
    return found


def _details(details: Details) -> dict[str, object]:
    """A cardio log's details as workout columns (ADR-0067)."""
    return {
        "effort": details.effort,
        "distance_m": details.distance_m,
        "avg_hr": details.avg_hr,
        "max_hr": details.max_hr,
        "started_at": details.started_at,
    }


def strength_on(session: Session, on: date, tz: ZoneInfo, template: SessionTemplate | None) -> bool:
    """Whether a log on ``on`` for ``template`` is filed under the strength prescription
    (ADR-0028): what a draft must carry, for drafts built elsewhere (the guided session)."""
    return _strength(session, on, tz, template)
