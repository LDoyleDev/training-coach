"""Builders for model rows: sensible defaults, override only what a test cares about."""

from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, LadderStep, SessionTemplate, TemplateItem
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.load import LoadKit
from training_coach.services.seed import load_plan


def exercise(session: Session, slug: str = "pull-up") -> Exercise:
    row = Exercise(slug=slug, name="Pull-up", kind=ExerciseKind.REPS)
    row.ladder = [
        LadderStep(position=0, name="Negatives"),
        LadderStep(position=1, name="Strict"),
    ]
    session.add(row)
    session.flush()
    return row


def template(session: Session, of: Exercise, position: int = 0) -> SessionTemplate:
    row = SessionTemplate(position=position, slug=f"upper-{position}", name="Upper", focus="x")
    row.items = [TemplateItem(position=0, exercise_id=of.id, sets=4, rep_min=5, rep_max=12)]
    session.add(row)
    session.flush()
    return row


def loads(slug: str, kit: LoadKit) -> dict[tuple[str, str], LoadKit]:
    """Every step of one bundled exercise as if it took load with ``kit`` (ADR-0072): patch it
    over ``blocks._load_kits``."""
    ladder = next(e.ladder for e in load_plan().exercises if e.slug == slug)
    return {(slug, step): kit for step in ladder}
