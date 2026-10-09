"""Web sign-in (ADR-0036): one-time links from the bot, and the sessions they start.

Tokens are 32 random bytes, handed out once and stored only as SHA-256 hashes. Which person a
token belongs to is the question being asked, so those lookups run in an unbound session with
``ALL_USERS`` (ADR-0029); every row they create names its user.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.orm import Session

from training_coach.db.models import LoginLink, WebSession
from training_coach.db.session import ALL_USERS

LINK_TTL = timedelta(minutes=10)
SESSION_TTL = timedelta(days=30)
RENEW_AFTER = timedelta(days=1)  # touch a session at most once a day: SQLite is on an SD card
LABEL_LENGTH = 120
EVERYONE = {ALL_USERS: True}


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_link(session: Session, now: datetime) -> str:
    """A sign-in link token for the user ``session`` is bound to; valid once, for 10 minutes."""
    token = secrets.token_urlsafe(32)
    session.add(LoginLink(token_hash=hash_token(token), expires_at=now + LINK_TTL))
    session.flush()
    return token


def redeem_link(session: Session, token: str, now: datetime, label: str) -> str | None:
    """Exchange a link token for a session token, or None if it's unknown, used or expired.
    ``session`` is unbound: the link says whose it is."""
    digest = hash_token(token)
    # Claimed in one conditional statement: of two racing redeems, only one changes the row.
    claimed = cast(
        "CursorResult[object]",
        session.execute(
            update(LoginLink)
            .where(
                LoginLink.token_hash == digest,
                LoginLink.used_at.is_(None),
                LoginLink.expires_at > now,
            )
            .values(used_at=now),
            execution_options=EVERYONE,
        ),
    )
    if claimed.rowcount != 1:
        return None
    user = session.scalars(  # the row this statement just claimed
        select(LoginLink.user_id).where(LoginLink.token_hash == digest), execution_options=EVERYONE
    ).one()
    return start_session(session, user, now, label)


def start_session(session: Session, user_id: int, now: datetime, label: str) -> str:
    """A new signed-in browser for ``user_id``: the cookie token, which is stored only hashed.
    Called once a link or a passkey has proved who it is."""
    cookie = secrets.token_urlsafe(32)
    session.add(
        WebSession(
            user_id=user_id,
            token_hash=hash_token(cookie),
            label=label[:LABEL_LENGTH] or "Unknown browser",
            created_at=now,
            last_seen_at=now,
            expires_at=now + SESSION_TTL,
        )
    )
    session.flush()
    return cookie


def _live(session: Session, token: str, now: datetime) -> WebSession | None:
    found = session.scalar(
        select(WebSession).where(WebSession.token_hash == hash_token(token)),
        execution_options=EVERYONE,
    )
    if found is None or found.ended_at is not None or found.expires_at <= now:
        return None
    return found


@dataclass(frozen=True)
class Seen:
    user_id: int
    renewed: bool  # the session got another 30 days: the cookie must be sent again too


def session_user(session: Session, token: str, now: datetime) -> Seen | None:
    """Whose session a token is, or None. A session in use stays signed in: it is renewed for
    another 30 days, at most once a day. ``session`` is unbound."""
    found = _live(session, token, now)
    if found is None:
        return None
    renewed = now - found.last_seen_at >= RENEW_AFTER
    if renewed:
        found.last_seen_at = now
        found.expires_at = now + SESSION_TTL
    return Seen(found.user_id, renewed)


def end_session(session: Session, token: str, now: datetime) -> None:
    """Sign out: the token stops working at once. Unknown tokens are ignored."""
    found = _live(session, token, now)
    if found is not None:
        found.ended_at = now


@dataclass(frozen=True)
class Device:
    id: int
    label: str
    created_at: datetime
    last_seen_at: datetime
    current: bool  # the browser asking


def devices(session: Session, current_token: str, now: datetime) -> list[Device]:
    """The bound user's signed-in browsers, newest first; ended and expired ones are left out."""
    mine = hash_token(current_token)
    rows = session.scalars(
        select(WebSession)
        .where(WebSession.ended_at.is_(None), WebSession.expires_at > now)
        .order_by(WebSession.last_seen_at.desc(), WebSession.id.desc())
    )
    return [
        Device(row.id, row.label, row.created_at, row.last_seen_at, row.token_hash == mine)
        for row in rows
    ]


def end_device(session: Session, device_id: int, now: datetime) -> bool:
    """Sign a browser out by id; False if it isn't one of the bound user's live sessions."""
    row = session.scalar(
        select(WebSession).where(WebSession.id == device_id, WebSession.ended_at.is_(None))
    )
    if row is None:
        return False
    row.ended_at = now
    return True
