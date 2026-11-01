"""People (ADR-0026). Per-person lookups here assume a session bound to the user
(``db.session``), which filters them; they never take a user id themselves."""

from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, ExerciseState, PlanState, User, UserSettings
from training_coach.db.session import bound_user
from training_coach.domain import region

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
            # Not secrets, and the owner's own: say which account the history moved from and to.
            session.add(
                Event(
                    kind="users.owner_relinked",
                    user_id=OWNER,
                    payload={"from": owner.telegram_user_id, "to": telegram_user_id},
                )
            )
        owner.telegram_user_id = telegram_user_id
    return owner.id


def telegram_chat(session: Session, user_id: int) -> int | None:
    """The private chat to message ``user_id`` in, or None if they have no Telegram linked.
    Any session may ask: users aren't per-person rows."""
    user = session.get(User, user_id)
    return user.telegram_user_id if user is not None else None


def plan_state(session: Session) -> PlanState | None:
    return session.scalar(select(PlanState))


def settings_row(session: Session) -> UserSettings | None:
    return session.scalar(select(UserSettings))


def exercise_state(session: Session, exercise_id: int) -> ExerciseState | None:
    return session.scalar(select(ExerciseState).where(ExerciseState.exercise_id == exercise_id))


def seen_in_europe(session: Session, user_id: int, now: datetime) -> None:
    """A signed-in web visit by ``user_id`` from a listed country (ADR-0085): written at most
    once an hour. Only the person's own session cookie leads here (``api.auth.owner``)."""
    user = session.get(User, user_id)
    if user is not None and region.worth_writing(user.last_seen_in_europe, now):
        user.last_seen_in_europe = now


def served_remotely(session: Session, user_id: int, now: datetime) -> bool:
    """Whether the bot and the MCP endpoint serve ``user_id``: within 30 days of their last
    visit from Europe. Any session may ask: users aren't per-person rows."""
    user = session.get(User, user_id)
    return user is not None and region.serves_remotely(user.last_seen_in_europe, now)


def bot_served(session: Session, now: datetime) -> bool:
    """``served_remotely`` for the person a session is bound to (the bot's sessions)."""
    user = bound_user(session)
    return user is not None and served_remotely(session, user, now)


def country(session: Session, user_id: int) -> str | None:
    user = session.get(User, user_id)
    return user.country if user is not None else None


def set_country(session: Session, user_id: int, code: str) -> bool:
    """Record the country of residence; False (nothing kept) if it isn't on the list."""
    user = session.get(User, user_id)
    if user is None or not region.listed(code):
        return False
    user.country = code.strip().upper()
    return True
