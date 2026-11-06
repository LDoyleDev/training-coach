"""The owner's plan brought to ``plan.toml`` (program-builder.md Decided 1, ADR-0073): the seed no
longer changes anyone's sessions, so a change to the file waits here, as a list of what would
change, until the owner saves it as one version. It is the owner's alone."""

from dataclasses import dataclass
from datetime import date

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    PlanVersion,
    SessionProgress,
    SessionTemplate,
    TemplateItem,
)
from training_coach.db.session import bound_user
from training_coach.domain.enums import Place
from training_coach.services import guided
from training_coach.services.seed import ItemSeed, PlanSeed, SeedResult, sync_sessions
from training_coach.services.users import OWNER

log = structlog.get_logger(__name__)

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


def _changes(session: Session, plan: PlanSeed) -> list[str]:
    names = {e.slug: e.name for e in plan.exercises}
    rows = {t.slug: t for t in session.scalars(select(SessionTemplate))}
    lines = []
    for position, seed in enumerate(plan.sessions):
        template = rows.get(seed.slug)
        if template is None:
            lines.append(f"New session: {seed.name}")
            continue
        if template.name != seed.name:
            lines.append(f"{template.name}: now called {seed.name}")
        if template.position != position:
            lines.append(f"{seed.name}: moves to place {position + 1} in the cycle")
        if (
            template.focus != seed.focus
            or template.kind != seed.type
            or template.is_rest_optional != seed.is_rest_optional
        ):
            lines.append(f"{seed.name}: its focus or kind")
        versions = (
            (Place.HOME, template.items, seed.items),
            (Place.GYM, template.gym_items, seed.gym),
            (Place.AWAY, template.away_items, seed.away),
        )
        for place, stored, planned in versions:
            lines += _version_changes(
                f"{seed.name}{LABELS[place]}", _stored(stored), _planned(planned), names
            )
    return lines


def _blocked(session: Session, plan: PlanSeed, today: date) -> str | None:
    planned = {s.slug for s in plan.sessions}
    rows = session.scalars(select(SessionTemplate).order_by(SessionTemplate.position))
    gone = [t.name for t in rows if t.slug not in planned]
    if gone:
        # Sessions define the queue (ADR-0006), and workouts name them.
        return f"{', '.join(gone)} isn't in plan.toml, and a session can't be removed this way."
    known = set(session.scalars(select(Exercise.slug)))
    used = {i.exercise for s in plan.sessions for i in s.versions}
    if used - known:
        return "plan.toml's new exercises aren't in the catalogue yet: the seed hasn't run."
    today_row = session.scalar(
        select(SessionProgress).where(
            SessionProgress.local_date == today, SessionProgress.saved_workout_id.is_(None)
        )
    )
    if (today_row is not None and today_row.sets) or guided.pending(session, today):
        return IN_PROGRESS
    return None


def preview(session: Session, plan: PlanSeed, today: date) -> Preview:
    """What saving would change for the person this session is bound to. Nothing for anyone but
    the owner, who alone has a plan that follows the file."""
    if bound_user(session) != OWNER:
        return Preview(())
    changes = _changes(session, plan)
    if not changes:
        return Preview(())
    return Preview(
        tuple(changes),
        _blocked(session, plan, today),
        plan.versions[-1].name if plan.versions else None,
    )


def save(session: Session, plan: PlanSeed, today: date) -> Preview:
    """Make the change, as one version dated ``today``: a second save that day updates it, and
    workouts keep the version they have. Returns what it changed; ``blocked`` set: nothing did."""
    found = preview(session, plan, today)
    if found.blocked or not found.changes:
        return found
    result = SeedResult()
    exercises = {e.slug: e for e in session.scalars(select(Exercise))}
    sync_sessions(session, plan, OWNER, exercises, result)
    name = found.version or "Imported from plan.toml"
    version = session.scalar(select(PlanVersion).where(PlanVersion.since == today))
    if version is None:
        session.add(PlanVersion(since=today, name=name))
    else:
        version.name = name
    session.add(Event(kind="plan.imported", payload={"changes": len(found.changes)}))
    log.info("plan.imported", changes=len(found.changes))
    return found
