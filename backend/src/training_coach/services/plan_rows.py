"""The plan as this person's rows say it is: the Plan page and the body map read it here, not
from ``plan.toml`` (builder step 5, ADR-0073). What an exercise is (its muscles, its ladder)
stays in the catalogue."""

from dataclasses import dataclass
from datetime import date

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import SessionProgress, SessionTemplate, TemplateItem
from training_coach.services import guided
from training_coach.services.seed import bundled_plan

log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PlannedItem:
    exercise: str  # slug
    sets: int
    rep_min: int
    rep_max: int
    per_side: bool


@dataclass(frozen=True)
class PlannedSession:
    position: int
    slug: str
    name: str
    focus: str
    kind: str  # strength | conditioning | recovery
    optional: bool
    items: tuple[PlannedItem, ...]  # the home version
    gym: tuple[PlannedItem, ...]  # empty: done the same way at the gym


def session_in_progress(session: Session, today: date) -> bool:
    """Kept sets wait to be saved, today or from a day before: they hold item positions, which a
    change to the plan would shift (ADR-0073)."""
    row = session.scalar(
        select(SessionProgress).where(
            SessionProgress.local_date == today, SessionProgress.saved_workout_id.is_(None)
        )
    )
    return bool(row is not None and row.sets) or bool(guided.pending(session, today))


def _items(rows: list[TemplateItem], known: set[str]) -> tuple[PlannedItem, ...]:
    """The version's items the catalogue knows. The seed refuses to drop an exercise in use, but
    a failed seed doesn't stop the app (ADR-0015), and one row mustn't take the page down."""
    found = []
    for item in rows:
        if item.exercise.slug in known:
            found.append(
                PlannedItem(
                    item.exercise.slug, item.sets, item.rep_min, item.rep_max, item.per_side
                )
            )
        else:
            log.warning("plan.exercise_not_in_catalogue", exercise=item.exercise.slug)
    return tuple(found)


def planned_sessions(session: Session) -> list[PlannedSession]:
    """The cycle in order, each session with its home and gym versions."""
    known = {e.slug for e in bundled_plan().exercises}
    found = session.scalars(
        select(SessionTemplate)
        .order_by(SessionTemplate.position)
        .options(
            selectinload(SessionTemplate.items).selectinload(TemplateItem.exercise),
            selectinload(SessionTemplate.gym_items).selectinload(TemplateItem.exercise),
        )
    )
    return [
        PlannedSession(
            position=template.position,
            slug=template.slug,
            name=template.name,
            focus=template.focus,
            kind=template.kind,
            optional=template.is_rest_optional,
            items=_items(template.items, known),
            gym=_items(template.gym_items, known),
        )
        for template in found
    ]
