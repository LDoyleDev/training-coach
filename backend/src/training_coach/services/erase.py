"""Erasing everything stored about a person (ADR-0044).

Deleting the user row takes every per-person row with it: each one's ``user_id`` is
``ON DELETE CASCADE`` (a test holds every ``Owned`` table to that). The person then starts
again under the same id and Telegram account, with the plan's starting rows, so the bot and the
web app keep working. Shared rows (the plan) are untouched.
"""

import structlog
from sqlalchemy.orm import Session

from training_coach.db.models import Event, User
from training_coach.services.seed import PlanSeed, apply_seed

log = structlog.get_logger(__name__)


def erase(session: Session, user_id: int, plan: PlanSeed) -> bool:
    """Erase the person's data and give them a fresh start. Runs in an unbound session (it
    deletes the user row itself). False if there is no such person."""
    user = session.get(User, user_id)
    if user is None:
        return False
    telegram = user.telegram_user_id
    session.delete(user)
    session.flush()  # the cascade runs here, in the database
    session.expunge_all()  # rows loaded before it are gone
    session.add(User(id=user_id, telegram_user_id=telegram))
    session.flush()
    apply_seed(session, plan)
    # Nothing about what was there: only that it was erased, as the history starts again.
    session.add(Event(user_id=user_id, kind="account.erased", payload={}))
    log.info("account.erased")
    return True
