"""Invites (ADR-0059): a one-time link an admin makes for someone to join, and joining with it.

A token is 32 random bytes in the link's fragment, stored only as SHA-256, valid 72 hours,
single use (claimed by one conditional update) and revocable. An invite makes a member, never an
admin. At most ``max_members`` people besides the owner, open invites counted, so a full house
can't be passed by inviting ahead. Joining creates the person with everything the seed gives a
new person and starts their web session. The admin sees members' labels and join days and the
open invites, nothing of anyone's data.

Invites and people are shared tables, so this runs in an unbound session; every per-person row
it creates names its person, as the seed's do.
"""

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

import structlog
from sqlalchemy import ColumnElement, CursorResult, func, select, update
from sqlalchemy.orm import Session

from training_coach.db.models import Event, Exercise, Invite, User
from training_coach.services import auth
from training_coach.services.seed import SeedResult, bundled_plan, start_person
from training_coach.services.users import MEMBER

log = structlog.get_logger(__name__)

INVITE_TTL = timedelta(hours=72)
FULL = "full"  # no room for another member


@dataclass(frozen=True)
class OpenInvite:
    id: int
    label: str | None
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class Member:
    user_id: int
    label: str | None
    joined: datetime


@dataclass(frozen=True)
class Joined:
    user_id: int
    cookie: str
    label: str | None
    invited_by: int  # the admin to tell


def members(session: Session) -> list[Member]:
    """Everyone but the admins, oldest first: their label and the day they joined, nothing more."""
    rows = session.scalars(select(User).where(User.role == MEMBER).order_by(User.created_at))
    return [Member(u.id, u.label, u.created_at) for u in rows]


def _open(now: datetime) -> ColumnElement[bool]:
    return (Invite.used_at.is_(None)) & (Invite.revoked_at.is_(None)) & (Invite.expires_at > now)


def open_invites(session: Session, now: datetime) -> list[OpenInvite]:
    rows = session.scalars(select(Invite).where(_open(now)).order_by(Invite.created_at))
    return [OpenInvite(i.id, i.label, i.created_at, i.expires_at) for i in rows]


def _taken(session: Session, now: datetime) -> int:
    open_count = session.scalar(select(func.count()).select_from(Invite).where(_open(now))) or 0
    return len(members(session)) + open_count


def make(
    session: Session, admin_id: int, label: str | None, now: datetime, max_members: int
) -> str | None:
    """A new invite's token, shown once; None when members and open invites fill the house."""
    if _taken(session, now) >= max_members:
        return None
    token = secrets.token_urlsafe(32)
    session.add(
        Invite(
            token_hash=auth.hash_token(token),
            label=label or None,
            created_by=admin_id,
            created_at=now,
            expires_at=now + INVITE_TTL,
        )
    )
    session.flush()
    log.info("invites.made")
    return token


def revoke(session: Session, invite_id: int, now: datetime) -> bool:
    """Whether an open invite was revoked: a used or expired one stays as it is."""
    done = session.execute(
        update(Invite).where(Invite.id == invite_id, _open(now)).values(revoked_at=now)
    )
    return cast("CursorResult[object]", done).rowcount == 1


def redeem(
    session: Session, token: str, now: datetime, device: str, max_members: int
) -> Joined | str | None:
    """Join with ``token``: the new member, signed in. None for a token that isn't an open
    invite (unknown, used, revoked or expired); ``FULL`` when there's no room, which leaves the
    invite unused."""
    digest = auth.hash_token(token)
    if len(members(session)) >= max_members:
        return (
            FULL
            if session.scalar(select(Invite.id).where(Invite.token_hash == digest, _open(now)))
            else None
        )
    claimed = session.execute(
        update(Invite).where(Invite.token_hash == digest, _open(now)).values(used_at=now)
    )
    if cast("CursorResult[object]", claimed).rowcount != 1:
        return None
    invite = session.scalars(select(Invite).where(Invite.token_hash == digest)).one()
    person = User(role=MEMBER, label=invite.label, created_at=now)
    session.add(person)
    session.flush()
    invite.used_by = person.id
    exercises = {e.slug: e for e in session.scalars(select(Exercise))}
    start_person(session, bundled_plan(), person.id, exercises, SeedResult())
    session.add(Event(kind="invites.used", user_id=person.id, payload={}))
    cookie = auth.start_session(session, person.id, now, device)
    log.info("invites.used")
    return Joined(person.id, cookie, invite.label, invite.created_by)
