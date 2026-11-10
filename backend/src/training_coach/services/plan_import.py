"""The owner's plan brought to ``plan.toml`` (program-builder.md Decided 1, ADR-0073): the seed no
longer changes anyone's sessions, so a change to the file waits here, as a list of what would
change, until the owner saves it as one version. It is the owner's alone.

The file is his whole plan (ADR-0093 Decided 14): a session it lacks is removed as the editor
removes one, and a retired session it has is put back."""

from dataclasses import dataclass
from datetime import date

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    PlanVersion,
    SessionTemplate,
    TemplateItem,
)
from training_coach.db.session import bound_user
from training_coach.domain import cycle as cycle_rules
from training_coach.domain.cycle import Applied, Slot
from training_coach.domain.enums import Place
from training_coach.services import plan_edit
from training_coach.services.plan_edit import Added, Kept
from training_coach.services.plan_rows import session_in_progress
from training_coach.services.seed import ItemSeed, PlanSeed, SeedResult, sync_sessions
from training_coach.services.users import OWNER

log = structlog.get_logger(__name__)

FIX = "Fix plan.toml first. "  # the file can't be a plan as it is (Decided 13 and 14)
IN_PROGRESS = "Finish or discard your session in progress first: its sets follow today's list."
LABELS = {Place.HOME: "", Place.GYM: " (gym)", Place.AWAY: " (away)"}
# An item as the plan and the rows both say it: exercise slug, sets, reps, per side and pair.
Facts = tuple[str, int, int, int, bool, int | None]


@dataclass(frozen=True)
class Preview:
    changes: tuple[str, ...]  # what saving would change, in words; empty when the plan matches
    blocked: str | None = None  # why it can't be saved now
    version: str | None = None  # what the new version would be called


def _stored(items: list[TemplateItem]) -> list[Facts]:
    return [(i.exercise.slug, i.sets, i.rep_min, i.rep_max, i.per_side, i.pair) for i in items]


def _planned(items: tuple[ItemSeed, ...] | list[ItemSeed]) -> list[Facts]:
    return [(i.exercise, i.sets, i.rep_min, i.rep_max, i.per_side, i.pair) for i in items]


def _version_changes(
    label: str, old: list[Facts], new: list[Facts], names: dict[str, str]
) -> list[str]:
    def amount(item: Facts) -> str:
        return f"{item[1]} x {item[2]}-{item[3]}"

    lines = []
    for position in range(max(len(old), len(new))):
        was = old[position] if position < len(old) else None
        now = new[position] if position < len(new) else None
        if was == now:
            continue
        if was is None and now is not None:
            lines.append(f"{label}: adds {names[now[0]]}, {amount(now)}")
        elif now is None and was is not None:
            lines.append(f"{label}: drops {names.get(was[0], was[0])}")
        elif was is not None and now is not None:
            before = names.get(was[0], was[0])
            if was[0] != now[0]:
                lines.append(f"{label}: {before} becomes {names[now[0]]}, {amount(now)}")
            elif amount(was) != amount(now):
                lines.append(f"{label}: {before}, {amount(was)} becomes {amount(now)}")
            else:
                lines.append(f"{label}: {before}, how it's done or paired")
    return lines


@dataclass(frozen=True)
class _Cycle:
    """The owner's sessions against the file's: a session in the draft by its id when it is in
    the cycle, by its slug when it is new or put back."""

    live: dict[str, SessionTemplate]  # in the cycle now, by slug, in order
    back: dict[str, SessionTemplate]  # retired, and the file has them: put back
    gone: list[SessionTemplate]  # in the cycle, and the file lacks them: removed
    logged: set[int]  # the removed ones a workout names: retired, not deleted (Decided 5)
    draft: plan_edit.Draft
    applied: Applied


def _cycle(session: Session, plan: PlanSeed) -> _Cycle | str:
    """The cycle the file makes, or why it can't be one, in words (Decided 13)."""
    rows = plan_edit.templates(session, retired=True)
    planned = {s.slug for s in plan.sessions}
    live = {t.slug: t for t in rows if t.retired_on is None}
    back = {t.slug: t for t in rows if t.retired_on is not None and t.slug in planned}
    gone = [t for t in live.values() if t.slug not in planned]
    kept: dict[int, Kept] = {}
    added: dict[str, Added] = {}
    slots: list[Slot] = []
    for seed in plan.sessions:
        row = live.get(seed.slug)
        if row is None:
            added[seed.slug] = Added(seed.slug, seed.name, seed.type, seed.rest_after)
            slots.append(Slot(seed.slug, seed.rest_after))
        else:
            kept[row.id] = Kept(seed.slug, seed.name, seed.type, seed.rest_after)
            slots.append(Slot(row.id, seed.rest_after))
    problem = cycle_rules.problem(slots)
    if problem is not None:
        return problem
    applied = plan_edit.queue_after(session, list(live.values()), slots)
    logged = plan_edit.logged(session, [t.id for t in gone])
    return _Cycle(live, back, gone, logged, plan_edit.Draft(tuple(slots), kept, added), applied)


def _changes(plan: PlanSeed, cycle: _Cycle) -> list[str]:
    names = {e.slug: e.name for e in plan.exercises}
    lines = []
    for position, seed in enumerate(plan.sessions):
        if seed.slug in cycle.back:
            lines.append(f"Puts back {seed.name}")
            continue
        template = cycle.live.get(seed.slug)
        if template is None:
            lines.append(f"New session: {seed.name}")
            continue
        if template.name != seed.name:
            lines.append(f"{template.name}: now called {seed.name}")
        if template.id in cycle.applied.moved:  # not the ones an add or a removal shifts
            lines.append(f"{seed.name}: moves to place {position + 1} in the cycle")
        if (
            template.focus != seed.focus
            or template.kind != seed.type
            or template.is_rest_optional != seed.is_rest_optional
        ):
            lines.append(f"{seed.name}: its focus or kind")
        if template.rest_after != seed.rest_after:
            lines.append(
                f"{seed.name}: rest days after it, {template.rest_after} becomes {seed.rest_after}"
            )
        versions = (
            (Place.HOME, template.items, seed.items),
            (Place.GYM, template.gym_items, seed.gym),
            (Place.AWAY, template.away_items, seed.away),
        )
        for place, stored, planned in versions:
            lines += _version_changes(
                f"{seed.name}{LABELS[place]}", _stored(stored), _planned(planned), names
            )
    for row in cycle.gone:
        kept = ": its history stays" if row.id in cycle.logged else ""
        lines.append(f"Removes {row.name}{kept}")
    return lines


def _blocked(session: Session, plan: PlanSeed, today: date) -> str | None:
    known = set(session.scalars(select(Exercise.slug)))
    used = {i.exercise for s in plan.sessions for i in s.versions}
    if used - known:
        return "plan.toml's new exercises aren't in the catalogue yet: the seed hasn't run."
    return IN_PROGRESS if session_in_progress(session, today) else None


def _preview(session: Session, plan: PlanSeed, today: date) -> tuple[Preview, _Cycle | None]:
    if bound_user(session) != OWNER:
        return Preview(()), None
    cycle = _cycle(session, plan)
    if isinstance(cycle, str):
        return Preview((), FIX + cycle), None
    changes = _changes(plan, cycle)
    if not changes:
        return Preview(()), None
    # The sessions after it are exactly the file's, so every name is checked (Decided 14).
    problem = plan_edit.names_problem([(s.name, True) for s in plan.sessions], plan, today)
    if problem is not None:
        return Preview((), FIX + problem), None
    found = Preview(
        tuple(changes),
        _blocked(session, plan, today),
        plan.versions[-1].name if plan.versions else None,
    )
    return found, cycle


def preview(session: Session, plan: PlanSeed, today: date) -> Preview:
    """What saving would change for the person this session is bound to. Nothing for anyone but
    the owner, who alone has a plan that follows the file. A file that can't be a plan (two
    sessions with one name, say) is refused in words, with nothing listed."""
    return _preview(session, plan, today)[0]


def save(session: Session, plan: PlanSeed, today: date) -> Preview:
    """Make the change, as one version dated ``today``: a second save that day updates it, and
    workouts keep the version they have. A session the file lacks is retired or deleted as the
    editor does it, and a retired one it has is put back, with the queue moved off the removed
    ones (Decided 9). Returns what it changed; ``blocked`` set: nothing did."""
    found, cycle = _preview(session, plan, today)
    if found.blocked or cycle is None:
        return found
    told = None  # read before the rows change: it names them as they were
    if cycle.applied.added or cycle.applied.removed:  # a session added, removed or put back
        by_id = {t.id: t for t in cycle.live.values()}
        told = plan_edit.notice(cycle.draft, by_id, cycle.applied, cycle.back.keys())
    result = SeedResult()
    exercises = {e.slug: e for e in session.scalars(select(Exercise))}
    plan_edit.retire([t for t in cycle.gone if t.id in cycle.logged], today)
    session.flush()
    sync_sessions(session, plan.sessions, OWNER, exercises, result)
    pointer = cycle.applied.pointer
    if isinstance(pointer, str):  # a new or put-back session, by its slug
        pointer = session.scalars(
            select(SessionTemplate.id).where(SessionTemplate.slug == pointer)
        ).one()
    gone = [t for t in cycle.gone if t.id not in cycle.logged]
    plan_edit.requeue(session, pointer, cycle.applied.queued, gone)
    name = found.version or "Imported from plan.toml"
    version = session.scalar(select(PlanVersion).where(PlanVersion.since == today))
    if version is None:
        session.add(PlanVersion(since=today, name=name))
    else:
        version.name = name
    session.add(Event(kind="plan.imported", payload={"changes": len(found.changes)}))
    plan_edit.tell(session, cycle.applied, len(cycle.logged), told)
    session.flush()
    log.info("plan.imported", changes=len(found.changes))
    return found
