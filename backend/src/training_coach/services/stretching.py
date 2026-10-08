"""The stretching routine for a session (#98, ADR-0032): the session's muscles from the plan,
the stretches from the bundled plan file, the choice from ``domain.stretching``."""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from training_coach.db.models import SessionTemplate, TemplateItem
from training_coach.domain.stretching import Step, routine
from training_coach.services.seed import bundled_plan


def worked(session: Session, template_id: int) -> Counter[str] | None:
    """Planned sets per muscle group in a session, or None if there's no such session."""
    template = session.scalar(
        select(SessionTemplate)
        .where(SessionTemplate.id == template_id)
        .options(selectinload(SessionTemplate.items).selectinload(TemplateItem.exercise))
    )
    if template is None:
        return None
    sets: Counter[str] = Counter()
    for item in template.items:
        for group in item.exercise.muscle_groups:
            sets[group] += item.sets
    return sets


def for_session(session: Session, template_id: int, minutes: int) -> list[Step] | None:
    """The routine after ``template_id`` in ``minutes``, or None if there's no such session."""
    muscles = worked(session, template_id)
    if muscles is None:
        return None
    return routine([s.stretch() for s in bundled_plan().stretches], muscles, minutes)
