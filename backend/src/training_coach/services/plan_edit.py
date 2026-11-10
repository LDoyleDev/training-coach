"""A person editing their own plan (builder step 6, program-builder.md F, ADR-0073): the draft is
in the browser, and nothing changes until Save, which replaces the session versions it names and
makes one plan version, with a short note of what changed.

Warnings stay warnings: a free builder lets someone plan 40 sets of chest, and only what the app
couldn't run is refused (an exercise not in the catalogue, an away version that needs kit)."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import structlog
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import (
    Event,
    Exercise,
    PlanVersion,
    SessionTemplate,
    TemplateItem,
)
from training_coach.db.session import bound_user
from training_coach.domain.enums import Place
from training_coach.domain.kit import need_label
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

log = structlog.get_logger(__name__)

STALE = "stale"  # the plan changed since this draft was loaded
IN_PROGRESS = "in-progress"  # kept sets hold item positions, which an edit would shift


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
class Saved:
    revision: str
    version: str | None  # the note it was saved under; None: nothing differed, so no version


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


def save(
    session: Session,
    edits: Sequence[VersionEdit],
    note: str,
    draft_of: str,
    plan: PlanSeed,
    today: date,
) -> Saved | str:
    """Replace the versions named and make one version dated ``today`` with ``note``: a second
    save that day adds its note to it. Workouts keep the version they have. Returns ``STALE``,
    ``IN_PROGRESS`` or why it is refused, in words, having changed nothing."""
    if revision(session) != draft_of:
        return STALE
    rows = {t.slug: t for t in templates(session)}
    exercises = {e.slug: e for e in session.scalars(select(Exercise))}
    # Only what's loaded: the seed can fail on a release's new exercise (the Dockerfile goes on).
    catalogue = {e.slug: e for e in plan.exercises if e.slug in exercises}
    for edit in edits:
        template = rows.get(edit.slug)
        if template is None:
            return f"{edit.slug} isn't one of your sessions."
        problem = _problem(edit, catalogue) or _pairs_problem(edit, template.name)
        if problem:
            return problem
    if not any(
        [_facts(i) for i in _versions(rows[edit.slug])[edit.place]] != list(edit.items)
        for edit in edits
    ):
        return Saved(draft_of, None)
    if session_in_progress(session, today):
        return IN_PROGRESS
    user = bound_user(session)
    assert user is not None  # noqa: S101 - a person's plan is edited through their bound session
    result = SeedResult()
    for edit in edits:
        sync_version(user, _versions(rows[edit.slug])[edit.place], _seeds(edit), exercises, result)
    version = session.scalar(select(PlanVersion).where(PlanVersion.since == today))
    if version is None:
        version = PlanVersion(since=today, name=note)
        session.add(version)
    else:
        version.name = _both(version.name, note)
    name = version.name
    session.add(Event(kind="plan.edited", payload={"versions": len(edits)}))
    session.flush()
    session.expire_all()
    log.info("plan.edited", versions=len(edits))
    return Saved(revision(session), name)
