"""Builders for model rows: sensible defaults, override only what a test cares about."""

from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, LadderStep, SessionTemplate, TemplateItem
from training_coach.domain.enums import ExerciseKind


def exercise(session: Session, slug: str = "pull-up") -> Exercise:
    row = Exercise(slug=slug, name="Pull-up", kind=ExerciseKind.REPS, muscle_groups=["back"])
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
