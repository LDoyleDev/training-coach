"""A person's home kit (ADR-0071, builder step 4): read it, save the whole list, ask what an item
would unlock, and look up the kit each ladder step needs (the catalogue's ``needs`` in the
bundled plan, ADR-0064). The rules are in ``domain.kit``; the caller owns the transaction.

A kit nobody has saved yet is ``None``: no step locks until the person lists theirs.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Equipment, Event, Exercise
from training_coach.domain import kit as domain
from training_coach.domain.kit import Item, Resistance
from training_coach.domain.muscles import Kit
from training_coach.services import users
from training_coach.services.seed import bundled_plan

SAVED = "equipment.saved"


def _item(row: Equipment) -> Item:
    return Item(
        kit=Kit(row.kit),
        kg=row.kg,
        min_kg=row.min_kg,
        resistance=Resistance(row.resistance) if row.resistance is not None else None,
        note=row.note,
    )


def items(session: Session) -> list[Item]:
    """The kit as listed, in the order it was saved; empty if nothing is listed."""
    return [_item(r) for r in session.scalars(select(Equipment).order_by(Equipment.id))]


def saved_at(session: Session) -> datetime | None:
    """When the kit was last saved; None if it never was."""
    prefs = users.settings_row(session)
    return prefs.kit_saved_at if prefs is not None else None


def kit(session: Session) -> list[Item] | None:
    """The kit the locks are judged against: None until the person has saved one."""
    return items(session) if saved_at(session) is not None else None


def save(session: Session, kit_items: Sequence[Item], now: datetime) -> str | None:
    """Replace the whole kit with ``kit_items``. Returns why it can't be saved (nothing is
    changed then), or None once saved. An empty list is a kit too: bodyweight only."""
    if (problem := domain.problems(kit_items)) is not None:
        return problem
    prefs = users.settings_row(session)
    if prefs is None:  # every person gets a settings row when they join
        return "no settings for this person"
    for row in session.scalars(select(Equipment)):
        session.delete(row)
    session.add_all(
        Equipment(
            kit=i.kit.value,
            kg=i.kg,
            min_kg=i.min_kg,
            resistance=i.resistance.value if i.resistance is not None else None,
            note=i.note,
        )
        for i in kit_items
    )
    prefs.kit_saved_at = now
    session.add(Event(kind=SAVED, payload={"items": len(kit_items)}))
    return None


def step_needs(slug: str) -> dict[str, list[str]]:
    """Ladder step name -> the kit it needs, for one exercise of the catalogue."""
    found = next((e for e in bundled_plan().exercises if e.slug == slug), None)
    return dict(found.needs) if found is not None else {}


def ladder_needs(exercise: Exercise) -> list[list[str]]:
    """Each of the exercise's ladder steps' needs, easiest first (a step the plan no longer
    lists needs nothing)."""
    needs = step_needs(exercise.slug)
    return [needs.get(step.name, []) for step in exercise.ladder]


@dataclass(frozen=True)
class Unlocked:
    exercise: str
    slug: str
    step: str


def unlocks(session: Session, adding: Item) -> list[Unlocked]:
    """The steps ``adding`` would open for this person, across the plan's exercises (not the
    retired ones), in plan file order."""
    plan = [e for e in bundled_plan().exercises if not e.retired]
    ladders = {e.slug: [(step, e.needs.get(step, [])) for step in e.ladder] for e in plan}
    names = {e.slug: e.name for e in plan}
    return [
        Unlocked(names[slug], slug, step)
        for slug, step in domain.unlocked(ladders, kit(session), adding)
    ]
