"""A person editing their own plan (builder step 6, program-builder.md F, ADR-0073): the draft is
in the browser, and nothing changes until Save, which replaces the session versions it names and
makes one plan version, with a short note of what changed.

Warnings stay warnings: a free builder lets someone plan 40 sets of chest, and only what the app
couldn't run is refused (an exercise not in the catalogue, an away version that needs kit)."""

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date

import structlog
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import (
    Event,
    Exercise,
    PlanNotice,
    PlanVersion,
    SessionTemplate,
    TemplateItem,
    Workout,
)
from training_coach.db.session import bound_user
from training_coach.domain import cycle as cycle_rules
from training_coach.domain.cycle import Applied, Key, Slot
from training_coach.domain.dates import date_line
from training_coach.domain.enums import Place
from training_coach.domain.kit import need_label
from training_coach.domain.muscles import Muscle, ranked
from training_coach.domain.parser import normalise_name
from training_coach.domain.queue import Position
from training_coach.services import today as queue_today
from training_coach.services import users
from training_coach.services.plan_rows import in_cycle, session_in_progress
from training_coach.services.seed import (
    GYM_LOADS,
    ExerciseSeed,
    ItemSeed,
    PlanSeed,
    SeedResult,
    SessionSeed,
    away_problem,
    sync_version,
)
from training_coach.services.workout_log import TODAY_WORD

log = structlog.get_logger(__name__)

STALE = "stale"  # the plan changed since this draft was loaded
IN_PROGRESS = "in-progress"  # kept sets hold item positions, which an edit would shift
CYCLE_CHANGED = "plan.cycle_changed"  # sessions added, removed, moved or rest places changed
NEW = "new:"  # a version of a new session names it by its draft key: "new:n1"
NAME_MAX = 40  # ADR-0093 Decided 3
KINDS = {"strength": "strength", "conditioning": "cardio", "recovery": "recovery"}  # in words


@dataclass(frozen=True)
class ItemEdit:
    exercise: str  # slug
    sets: int
    rep_min: int
    rep_max: int
    per_side: bool = False
    pair: int | None = None


@dataclass(frozen=True)
class VersionEdit:
    slug: str  # the session
    place: Place
    items: tuple[ItemEdit, ...]


@dataclass(frozen=True)
class EditableSession:
    slug: str
    name: str
    focus: str
    home: tuple[ItemEdit, ...]
    gym: tuple[ItemEdit, ...]  # empty: done the same way at the gym
    away: tuple[ItemEdit, ...]  # empty: no away version


@dataclass(frozen=True)
class Kept:
    """A saved session in a cycle draft, as it should be (ADR-0093)."""

    slug: str
    name: str
    kind: str  # strength | conditioning | recovery
    rest_after: int


@dataclass(frozen=True)
class Added:
    """A new session in a cycle draft, by the draft's own key ("n1") until Save makes its slug:
    empty, or a copy of a saved session's versions, focus and optional flag (Decided 2)."""

    key: str
    name: str
    kind: str
    rest_after: int
    copy_of: str | None = None  # a saved session's slug


@dataclass(frozen=True)
class Saved:
    revision: str
    version: str | None  # the note it was saved under; None: nothing differed, so no version
    slugs: Mapping[str, str] = field(default_factory=dict)  # a new session's key -> its slug


def _versions(template: SessionTemplate) -> dict[Place, list[TemplateItem]]:
    return {
        Place.HOME: template.items,
        Place.GYM: template.gym_items,
        Place.AWAY: template.away_items,
    }


def _facts(item: TemplateItem) -> ItemEdit:
    return ItemEdit(
        item.exercise.slug, item.sets, item.rep_min, item.rep_max, item.per_side, item.pair
    )


def templates(session: Session, *, retired: bool = False) -> list[SessionTemplate]:
    """This person's sessions in the cycle in order, with their versions and each item's
    exercise; with ``retired``, the retired ones too, parked last (ADR-0093)."""
    query = select(SessionTemplate) if retired else select(SessionTemplate).where(in_cycle())
    return list(
        session.scalars(
            query.order_by(SessionTemplate.position).options(
                selectinload(SessionTemplate.items).selectinload(TemplateItem.exercise),
                selectinload(SessionTemplate.gym_items).selectinload(TemplateItem.exercise),
                selectinload(SessionTemplate.away_items).selectinload(TemplateItem.exercise),
            )
        )
    )


def editable(session: Session) -> list[EditableSession]:
    return [
        EditableSession(
            t.slug,
            t.name,
            t.focus,
            tuple(_facts(i) for i in t.items),
            tuple(_facts(i) for i in t.gym_items),
            tuple(_facts(i) for i in t.away_items),
        )
        for t in templates(session)
    ]


def revision(session: Session) -> str:
    """What the plan is now, as a short hash: a draft names the one it was made from, so a save
    from a tab left open can't overwrite an edit made since (as a day clash asks, ADR-0060).
    Each session's name, kind, rest days and retired day count, retired sessions included
    (ADR-0093)."""
    state = [
        [
            t.slug,
            t.position,
            t.name,
            t.kind,
            t.rest_after,
            t.retired_on.isoformat() if t.retired_on is not None else None,
            {
                place.value: [_facts(i).__dict__ for i in items]
                for place, items in _versions(t).items()
            },
        ]
        for t in templates(session, retired=True)
    ]
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()[:16]


def places_for(exercise: ExerciseSeed) -> list[Place]:
    """Where the exercise can go: every gym has everything (ADR-0071), a barbell or a machine is
    only the gym's, and an away version asks for no kit (ADR-0086)."""
    gym_only = bool(set(exercise.loads.values()) & GYM_LOADS)
    found = [Place.GYM]
    if not gym_only:
        found.insert(0, Place.HOME)
    if away_problem(exercise) is None:
        found.append(Place.AWAY)
    return found


def level_range(exercise: ExerciseSeed) -> tuple[int, int] | None:
    """Who the exercise is for, from its first step's level to its last (ADR-0083)."""
    found = [exercise.levels[s] for s in exercise.ladder if s in exercise.levels]
    return (min(found), max(found)) if found else None


def first_needs(exercise: ExerciseSeed) -> list[str]:
    """What its first step needs, in words: where a person would start with the least kit."""
    return [need_label(need) for need in exercise.needs.get(exercise.ladder[0], [])]


def _problem(edit: VersionEdit, catalogue: dict[str, ExerciseSeed]) -> str | None:
    """Why this version can't be saved, in words; None when it can."""
    if edit.place is Place.HOME and not edit.items:
        return "A session needs at least one exercise."
    for item in edit.items:
        exercise = catalogue.get(item.exercise)
        if exercise is None or exercise.retired:
            return f"{item.exercise} isn't in the catalogue."
        if edit.place not in places_for(exercise):
            return f"{exercise.name} can't be done {_where(edit.place)}."
    return None


def _where(place: Place) -> str:
    return {Place.HOME: "at home", Place.GYM: "at the gym", Place.AWAY: "away"}[place]


def _seeds(edit: VersionEdit) -> list[ItemSeed]:
    return [ItemSeed(**item.__dict__) for item in edit.items]


def _pairs_problem(edit: VersionEdit, name: str) -> str | None:
    """A pair is two neighbouring items (ADR-0031), as ``SessionSeed`` holds the plan to."""
    try:
        SessionSeed.check_pairs(name, _seeds(edit))
    except ValidationError:
        return "Every range needs a low and a high, low first."
    except ValueError as exc:
        return str(exc)
    return None


def _both(earlier: str, note: str) -> str:
    """A day's version says all that changed that day, as far as its name holds: past that, the
    newest note."""
    joined = f"{earlier}; {note}"
    return note if earlier == note or len(joined) > PlanVersion.name.type.length else joined


@dataclass(frozen=True)
class _Draft:
    """A cycle draft checked against the saved sessions: each entry by its domain key."""

    slots: tuple[Slot, ...]
    kept: dict[int, Kept]  # by session id
    added: dict[str, Added]  # by draft key


def _name_problem(name: str, exercise_names: set[str], today: date) -> str | None:
    """Why a new or renamed session can't be called ``name`` (Decided 3): typed logs find a
    session by its name, so it can't read as an exercise or a day."""
    if not 1 <= len(name) <= NAME_MAX:
        return f"A session's name is 1 to {NAME_MAX} characters."
    if normalise_name(name) in exercise_names:
        return f"{name} is an exercise's name; pick another for a session."
    if date_line(name, today) is not None or TODAY_WORD.match(name):
        return f"{name} reads as a day in a typed log; pick another name."
    return None


def _draft(
    rows: Mapping[str, SessionTemplate],
    cycle: Sequence[Kept | Added],
    plan: PlanSeed,
    today: date,
) -> _Draft | str:
    """The draft by keys, or why it can't be saved, in words."""
    kept: dict[int, Kept] = {}
    added: dict[str, Added] = {}
    slots: list[Slot] = []
    for entry in cycle:
        key: Key
        if isinstance(entry, Kept):
            row = rows.get(entry.slug)
            if row is None:
                return f"{entry.slug} isn't one of your sessions."
            key = row.id
            kept[key] = entry
        else:
            if entry.copy_of is not None and entry.copy_of not in rows:
                return f"{entry.copy_of} isn't one of your sessions to copy."
            key = entry.key
            added[key] = entry
        if entry.kind not in KINDS:
            return "A session is strength, cardio or recovery."
        slots.append(Slot(key, entry.rest_after))
    problem = cycle_rules.problem(slots)
    if problem is not None:
        return problem
    exercise_names = {normalise_name(n) for e in plan.exercises for n in (e.name, *e.aliases)}
    seen: set[str] = set()
    for entry in cycle:
        renamed = isinstance(entry, Added) or rows[entry.slug].name != entry.name
        problem = _name_problem(entry.name, exercise_names, today) if renamed else None
        if problem is not None:
            return problem
        if normalise_name(entry.name) in seen:
            return f"Two sessions can't both be called {entry.name}."
        seen.add(normalise_name(entry.name))
    return _Draft(tuple(slots), kept, added)


def _slug(name: str, taken: set[str]) -> str:
    """A new session's slug, from its name (the seed's SLUG, at most 64): never one the
    person's rows have, retired ones included, nor a starter session's (``gym_version`` decides
    by slug), so "Three days A" becomes ``three-days-a-2``."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", plain).strip("-") or "session"
    found, n = base[:64].strip("-"), 1
    while found in taken:
        n += 1
        found = f"{base[: 63 - len(str(n))].strip('-')}-{n}"
    taken.add(found)
    return found


def _focus(items: Sequence[ItemEdit], catalogue: Mapping[str, ExerciseSeed], kind: str) -> str:
    """An empty session's focus (Decided 3): the two muscles its home items work most, in words,
    or its kind's word when they work none."""
    worked: dict[Muscle, float] = {}
    for item in items:
        for muscle, weight in catalogue[item.exercise].muscles.items():
            worked[muscle] = worked.get(muscle, 0.0) + weight * item.sets
    words = ", ".join(m.value for m, _ in ranked(worked)[:2]) or KINDS[kind]
    return words[0].upper() + words[1:]


def _rest_days(n: int) -> str:
    return "no rest days" if n == 0 else f"{n} rest day{'s' if n > 1 else ''}"


def _notice(draft: _Draft, by_id: Mapping[int, SessionTemplate], applied: Applied) -> str | None:
    """What a cycle change tells the person (Decided 10, ADR-0087), and what's next; None when
    no session was added, removed, renamed, moved, or given another kind or rest days."""
    said = [f"added {draft.added[key].name}" for key in applied.added]
    said += [f"removed {by_id[sid].name}" for sid in applied.removed]
    for sid, entry in draft.kept.items():
        row = by_id[sid]
        if entry.name != row.name:
            said.append(f"renamed {row.name} to {entry.name}")
        if sid in applied.moved:
            said.append(f"moved {entry.name}")
        if entry.kind != row.kind:
            said.append(f"made {entry.name} a {KINDS[entry.kind]} session")
        if entry.rest_after != row.rest_after:
            said.append(f"{entry.name} now has {_rest_days(entry.rest_after)} after it")
    if not said:
        return None
    pointer = applied.pointer
    upcoming = draft.added[pointer] if isinstance(pointer, str) else draft.kept[pointer]
    text = f"Your plan changed: {'; '.join(said)}. Next is {upcoming.name}."
    if len(text) > PlanNotice.text.type.length:
        text = f"Your plan changed: {len(said)} changes to your sessions. Next is {upcoming.name}."
    return text


@dataclass(frozen=True)
class _Write:
    """What saving a cycle needs beyond the draft and the queue after it."""

    by_id: Mapping[int, SessionTemplate]  # the live sessions before
    named: set[int]  # removed sessions a workout names: retired, not deleted
    focus: Mapping[str, str]  # an empty new session's, by draft key
    taken: set[str]  # slugs a new session can't have
    today: date


def _write_cycle(
    session: Session,
    draft: _Draft,
    applied: Applied,
    write: _Write,
    exercises: dict[str, Exercise],
    result: SeedResult,
) -> dict[str, SessionTemplate]:
    """Save the cycle (ADR-0093): retire what history names, rewrite every live position, make
    the new sessions, move the queue, then delete what nothing names. Returns the new sessions
    by draft key."""
    user = bound_user(session)
    assert user is not None  # noqa: S101 - checked by save
    for sid in applied.removed:
        if sid in write.named:  # history holds it: retired, as exercises are (Decided 5)
            row = write.by_id[sid]
            row.retired_on, row.position = write.today, 10_000 + sid
            row.items.clear()
            row.gym_items.clear()
            row.away_items.clear()
    session.flush()
    # Parked above every row, retired ones too, so no two share a position mid-update.
    park = max(t.position for t in templates(session, retired=True)) + 1
    for row in write.by_id.values():
        if row.retired_on is None:
            row.position += park
    session.flush()
    for sid, entry in draft.kept.items():
        row = write.by_id[sid]
        row.position, row.name, row.kind = applied.positions[sid], entry.name, entry.kind
        row.rest_after = entry.rest_after
    made: dict[str, SessionTemplate] = {}
    for key, new in draft.added.items():
        source = next((t for t in write.by_id.values() if t.slug == new.copy_of), None)
        row = SessionTemplate(
            user_id=user,
            slug=_slug(new.name, write.taken),
            position=applied.positions[key],
            name=new.name,
            focus=source.focus if source is not None else write.focus[key],
            kind=new.kind,
            is_rest_optional=source is not None and source.is_rest_optional,
            rest_after=new.rest_after,
        )
        session.add(row)
        if source is not None:  # a copy has all three versions (Decided 17)
            for place, items in _versions(source).items():
                seeds = [ItemSeed(**_facts(i).__dict__) for i in items]
                sync_version(user, _versions(row)[place], seeds, exercises, result)
        made[key] = row
    session.flush()
    state = users.plan_state(session)
    if state is not None:  # moved before a session it names goes
        pointer = applied.pointer
        state.next_template_id = made[pointer].id if isinstance(pointer, str) else pointer
        state.queued = list(applied.queued)
        session.flush()
    for sid in applied.removed:
        if sid not in write.named:  # nothing logged for it, so it goes (Decided 5)
            session.delete(write.by_id[sid])
    session.flush()
    return made


def save(
    session: Session,
    edits: Sequence[VersionEdit],
    note: str,
    draft_of: str,
    plan: PlanSeed,
    today: date,
    cycle: Sequence[Kept | Added] | None = None,
) -> Saved | str:
    """Replace the versions named and make one version dated ``today`` with ``note``: a second
    save that day adds its note to it. Workouts keep the version they have.

    With ``cycle``, the live sessions as they should be, in order (ADR-0093), saved in the same
    transaction: a session missing from it is removed, and ``edits`` may name a new one as
    ``new:<key>``. Returns ``STALE``, ``IN_PROGRESS`` or why it is refused, in words, having
    changed nothing."""
    if revision(session) != draft_of:
        return STALE
    rows = {t.slug: t for t in templates(session)}
    by_id = {t.id: t for t in rows.values()}
    exercises = {e.slug: e for e in session.scalars(select(Exercise))}
    # Only what's loaded: the seed can fail on a release's new exercise (the Dockerfile goes on).
    catalogue = {e.slug: e for e in plan.exercises if e.slug in exercises}
    draft = None
    if cycle is not None:
        found = _draft(rows, [replace(e, name=e.name.strip()) for e in cycle], plan, today)
        if isinstance(found, str):
            return found
        draft = found
    # Each version as it is now, by the slug an edit names: a new session's is its copy's.
    now: dict[str, tuple[str, dict[Place, list[ItemEdit]]]] = {}
    for t in rows.values():
        if draft is None or t.id in draft.kept:
            name = t.name if draft is None else draft.kept[t.id].name
            now[t.slug] = (name, {p: [_facts(i) for i in v] for p, v in _versions(t).items()})
    added = draft.added if draft is not None else {}
    for key, new in added.items():
        source = rows.get(new.copy_of or "")
        versions = _versions(source) if source is not None else {}
        now[NEW + key] = (new.name, {p: [_facts(i) for i in versions.get(p, [])] for p in Place})
    for edit in edits:
        if edit.slug not in now:
            return f"{edit.slug} isn't one of your sessions."
        problem = _problem(edit, catalogue) or _pairs_problem(edit, now[edit.slug][0])
        if problem:
            return problem
    homes = {e.slug: e.items for e in edits if e.place is Place.HOME}
    for key, new in added.items():
        if new.copy_of is None and NEW + key not in homes:
            return f"{new.name} needs at least one exercise."
    applied = notice = None
    if draft is not None:
        before = tuple(Slot(t.id, t.rest_after) for t in rows.values())
        position = queue_today.position(session) or Position(next(iter(by_id), 0))
        applied = cycle_rules.applied(before, draft.slots, position, queue_today.last_done(session))
        notice = _notice(draft, by_id, applied)
    if notice is None and all(now[e.slug][1][e.place] == list(e.items) for e in edits):
        return Saved(draft_of, None)
    if session_in_progress(session, today):
        return IN_PROGRESS
    user = bound_user(session)
    assert user is not None  # noqa: S101 - a person's plan is edited through their bound session
    result = SeedResult()
    made: dict[str, SessionTemplate] = {}
    named: set[int] = set()
    if draft is not None and applied is not None:
        removed = Workout.template_id.in_(applied.removed)
        named = {sid for sid in session.scalars(select(Workout.template_id).where(removed)) if sid}
        taken = set(session.scalars(select(SessionTemplate.slug)))
        taken |= {s.slug for starter in plan.starters for s in starter.sessions}
        focus = {k: _focus(homes.get(NEW + k, ()), catalogue, new.kind) for k, new in added.items()}
        write = _Write(by_id, named, focus, taken, today)
        made = _write_cycle(session, draft, applied, write, exercises, result)
    targets = {**rows, **{NEW + key: row for key, row in made.items()}}
    for edit in edits:
        place = _versions(targets[edit.slug])[edit.place]
        sync_version(user, place, _seeds(edit), exercises, result)
    version = session.scalar(select(PlanVersion).where(PlanVersion.since == today))
    if version is None:
        version = PlanVersion(since=today, name=note)
        session.add(version)
    else:
        version.name = _both(version.name, note)
    name = version.name
    session.add(Event(kind="plan.edited", payload={"versions": len(edits)}))
    if applied is not None and applied.changed:
        counts = {
            "added": len(applied.added),
            "removed": len(applied.removed),
            "retired": len(named),
            "moved": len(applied.moved),
        }
        session.add(Event(kind=CYCLE_CHANGED, payload=counts))
        log.info(CYCLE_CHANGED, **counts)
    if notice is not None:
        session.add(PlanNotice(text=notice))
    session.flush()
    slugs = {key: row.slug for key, row in made.items()}
    session.expire_all()
    log.info("plan.edited", versions=len(edits))
    return Saved(revision(session), name, slugs)
