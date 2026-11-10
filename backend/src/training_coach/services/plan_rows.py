"""The plan as this person's rows say it is: the Plan page and the body map read it here, not
from ``plan.toml`` (builder step 5, ADR-0073). What an exercise is (its muscles, its ladder)
stays in the catalogue."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date

import structlog
from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import SessionProgress, SessionTemplate, TemplateItem
from training_coach.domain.enums import Place

log = structlog.get_logger(__name__)


def in_cycle() -> ColumnElement[bool]:
    """The sessions in the cycle: not retired (ADR-0093). Every reader of the cycle filters by
    it; a reader of a name by id (history) doesn't, so a retired session keeps its name there."""
    return SessionTemplate.retired_on.is_(None)


# An id from a client (a pick menu left open, a Telegram button, the Log page, a proposal) that
# names a session no longer in the cycle, retired or deleted (ADR-0093 Decided 12).
GONE = "That session is no longer in your plan"


def in_plan(session: Session, template_id: int) -> bool:
    """Whether ``template_id`` names a session in the cycle: not retired, not deleted."""
    found = session.scalar(
        select(SessionTemplate.id).where(SessionTemplate.id == template_id, in_cycle())
    )
    return found is not None


def _known() -> set[str]:
    # Imported here, not at the top: the seed, Today and the log import this module for
    # ``in_cycle``, and the seed and guided (which imports Today) would make it a circle.
    from training_coach.services.seed import bundled_plan

    return {e.slug for e in bundled_plan().exercises}


@dataclass(frozen=True)
class PlannedItem:
    exercise: str  # slug
    sets: int
    rep_min: int
    rep_max: int
    per_side: bool
    pair: int | None = None


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
    rest_after: int = 0  # rest places after it in the queue (ADR-0091)


def session_in_progress(session: Session, today: date) -> bool:
    """Kept sets wait to be saved, today or from a day before: they hold item positions, which a
    change to the plan would shift (ADR-0073)."""
    row = session.scalar(
        select(SessionProgress).where(
            SessionProgress.local_date == today, SessionProgress.saved_workout_id.is_(None)
        )
    )
    from training_coach.services import guided  # imported here, as in _known

    return bool(row is not None and row.sets) or bool(guided.pending(session, today))


def _items(rows: list[TemplateItem], known: set[str]) -> tuple[PlannedItem, ...]:
    """The version's items the catalogue knows. The seed refuses to drop an exercise in use, but
    a failed seed doesn't stop the app (ADR-0015), and one row mustn't take the page down."""
    found = []
    for item in rows:
        if item.exercise.slug in known:
            found.append(
                PlannedItem(
                    item.exercise.slug,
                    item.sets,
                    item.rep_min,
                    item.rep_max,
                    item.per_side,
                    item.pair,
                )
            )
        else:
            log.warning("plan.exercise_not_in_catalogue", exercise=item.exercise.slug)
    return tuple(found)


def with_draft(
    sessions: list[PlannedSession], versions: Mapping[tuple[str, Place], Sequence[PlannedItem]]
) -> list[PlannedSession]:
    """The sessions as they would be with a draft's versions, by session slug and place; items
    the catalogue doesn't know are left out, as they are from the rows."""
    known = _known()

    def drafted(
        session: PlannedSession, place: Place, now: tuple[PlannedItem, ...]
    ) -> tuple[PlannedItem, ...]:
        found = versions.get((session.slug, place))
        return now if found is None else tuple(i for i in found if i.exercise in known)

    return [
        replace(s, items=drafted(s, Place.HOME, s.items), gym=drafted(s, Place.GYM, s.gym))
        for s in sessions
    ]


def planned_sessions(session: Session) -> list[PlannedSession]:
    """The cycle in order, each session with its home and gym versions."""
    known = _known()
    found = session.scalars(
        select(SessionTemplate)
        .where(in_cycle())
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
            rest_after=template.rest_after,
        )
        for template in found
    ]
