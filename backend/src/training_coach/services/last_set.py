"""Last set: as many good reps as you can (ADR-0084): whether a person can have it yet, and
whether it is on for them. The rules are in ``domain.last_set``."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import Workout
from training_coach.domain import last_set
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import user_settings

LOCKED = "Available after your first 8 weeks"


def available(session: Session, today: date) -> bool:
    """Whether the option can be on: 8 weeks after the person's first logged workout."""
    first = session.scalar(
        select(func.min(Workout.local_date)).where(Workout.status == WorkoutStatus.DONE)
    )
    return last_set.available(first, today)


def live(session: Session, today: date) -> bool | None:
    """The person's setting while the option is available; None while it is locked."""
    return user_settings.load(session).last_set_amrap if available(session, today) else None
