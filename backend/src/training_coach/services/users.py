"""People (ADR-0026). Per-person lookups here assume a session bound to the user
(``db.session``), which filters them; they never take a user id themselves."""

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import ExerciseState, PlanState, User, UserSettings

log = structlog.get_logger(__name__)

OWNER = 1  # created by the migration that added users; phase 1 has only this person


def link_owner(session: Session, telegram_user_id: int) -> int:
    """The owner's user id, linked to the allowed Telegram account (ADR-0009). Run in an
    unbound session at start-up. If the allowed account changed, the owner moves with it."""
    owner = session.get(User, OWNER)
    if owner is None:  # a database created before the users migration can't get here
        owner = User(id=OWNER)
        session.add(owner)
    if owner.telegram_user_id != telegram_user_id:
        if owner.telegram_user_id is not None:
            log.warning("users.owner_relinked")
        owner.telegram_user_id = telegram_user_id
    return owner.id


def plan_state(session: Session) -> PlanState | None:
    return session.scalar(select(PlanState))


def settings_row(session: Session) -> UserSettings | None:
    return session.scalar(select(UserSettings))


def exercise_state(session: Session, exercise_id: int) -> ExerciseState | None:
    return session.scalar(select(ExerciseState).where(ExerciseState.exercise_id == exercise_id))
