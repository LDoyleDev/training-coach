"""Erasing everything stored about a person (ADR-0044), and a member leaving (ADR-0088).

Deleting the user row takes every per-person row with it: each one's ``user_id`` is
``ON DELETE CASCADE`` (a test holds every ``Owned`` table to that). The person then starts
again under the same id and role, with a starter (ADR-0073), so the web app keeps working. The
owner keeps their Telegram account, which the bot is set up for; a member's link goes with the
rest, and they connect again from Account (ADR-0059's 2026-11-07 addendum). The catalogue and
everyone else's rows are untouched.

A member leaving goes the same way with no fresh start, and is put on the left list first, so a
restored backup can't quietly bring them back.
"""

from datetime import datetime
from pathlib import Path

import structlog
from sqlalchemy import delete
from sqlalchemy.orm import Session

from training_coach.db.models import Event, Invite, PlanState, User, Workout
from training_coach.db.session import ALL_USERS
from training_coach.services import left_list
from training_coach.services.seed import PlanSeed, apply_seed
from training_coach.services.users import MEMBER, OWNER

log = structlog.get_logger(__name__)


def erase(session: Session, user_id: int, plan: PlanSeed) -> bool:
    """Erase the person's data and give them a fresh start. Runs in an unbound session (it
    deletes the user row itself). False if there is no such person."""
    user = session.get(User, user_id)
    if user is None:
        return False
    telegram = user.telegram_user_id if user_id == OWNER else None
    seen = user.last_seen_in_europe
    role, label, joined = user.role, user.label, user.created_at
    _delete(session, user)
    # The country of residence goes with the rest (asked again). "Last seen in Europe" is kept:
    # an erase sent without a country (LAN, Tailscale) mustn't restart the 30 days (ADR-0085).
    # Who they are to the app is kept, not being their data: role, label and join day (ADR-0059),
    # so the owner erasing stays the admin, not a new member.
    session.add(
        User(
            id=user_id,
            telegram_user_id=telegram,
            last_seen_in_europe=seen,
            role=role,
            label=label,
            created_at=joined,
        )
    )
    session.flush()
    apply_seed(session, plan)
    # Nothing about what was there: only that it was erased, as the history starts again.
    session.add(Event(user_id=user_id, kind="account.erased", payload={}))
    log.info("account.erased")
    return True


def leave(session: Session, user_id: int, left: Path | None, now: datetime) -> bool:
    """A member leaving, or removed by an admin (ADR-0088): everything of theirs goes, with no
    fresh start. Only members: the owner erases instead. ``left`` is the left list's file (None
    only without a database file). Runs in an unbound session. False if there is no such member."""
    user = session.get(User, user_id)
    if user is None or user.role != MEMBER:
        return False
    if left is not None:  # before the delete: a failed delete leaves them listed, never unlisted
        left_list.record(left, user_id, user.created_at, now)
    # The invite they came with held their label: it goes too.
    session.execute(delete(Invite).where(Invite.used_by == user_id))
    _delete(session, user)
    log.info("account.left")
    return True


def forget(session: Session, user_id: int) -> None:
    """Delete someone who left and came back with a restored backup (``forget-left``)."""
    user = session.get(User, user_id)
    if user is not None:
        session.execute(delete(Invite).where(Invite.used_by == user_id))
        _delete(session, user)
        log.info("account.forgotten")


def _delete(session: Session, user: User) -> None:
    # These RESTRICT the person's sessions and versions, and a RESTRICT fires even inside the
    # cascade, whichever table it reaches first: so they go first.
    for model in (PlanState, Workout):
        session.execute(
            delete(model).where(model.user_id == user.id), execution_options={ALL_USERS: True}
        )
    session.delete(user)
    session.flush()  # the cascade runs here, in the database
    session.expunge_all()  # rows loaded before it are gone
