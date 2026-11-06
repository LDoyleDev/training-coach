"""The plan as this person's rows say it is: the Plan page and the body map read it here, not
from ``plan.toml`` (builder step 5, ADR-0073). What an exercise is (its muscles, its ladder)
stays in the catalogue."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import SessionTemplate, TemplateItem


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


def _items(rows: list[TemplateItem]) -> tuple[PlannedItem, ...]:
    return tuple(
        PlannedItem(item.exercise.slug, item.sets, item.rep_min, item.rep_max, item.per_side)
        for item in rows
    )


def planned_sessions(session: Session) -> list[PlannedSession]:
    """The cycle in order, each session with its home and gym versions."""
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
            items=_items(template.items),
            gym=_items(template.gym_items),
        )
        for template in found
    ]
