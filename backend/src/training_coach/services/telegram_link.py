"""A member connecting their Telegram (ADR-0089): a link made on Account, opened in Telegram,
confirmed on Account with the code the bot sent.

The link is a ``t.me/<bot>?start=<token>`` token: 32 random bytes, stored only as SHA-256, 10
minutes, only the newest. ``/start <token>`` doesn't connect anything: it records the sender as
a claim and the bot sends them a 6-digit code. The member types the code their own Telegram
shows on Account, and Confirm connects the account it was sent to. A link takes at most 3
claims, its codes are unique within it and stored hashed, 5 wrong codes end it, and with more
than one claim it can't be confirmed: someone else has the link, so the member starts again.
So a forwarded link does nothing without a code typed in the member's own signed-in browser.

Everything here but ``claim`` runs in a session bound to the member. ``claim`` comes from a
sender who isn't anyone yet, so it runs unbound and finds whose link the token is.
"""

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast

import structlog
from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.orm import Session

from training_coach.db.models import Event, TelegramClaim, TelegramLink, User
from training_coach.services import auth

log = structlog.get_logger(__name__)

LINK_TTL = timedelta(minutes=10)
MAX_CLAIMS = 3
MAX_WRONG = 5
NAME_LENGTH = 64  # Telegram's own limit for a first name
LINKED = "telegram.linked"  # events in the member's own history
UNLINKED = "telegram.unlinked"
# Why a code or a confirm was refused.
NO_LINK = "no-link"  # none open: never made, cancelled, expired, ended or used
SHARED = "shared"  # more than one claim: someone else has the link
WRONG = "wrong"  # no claim has that code
ENDED = "ended"  # that was the fifth wrong code: the link is gone
TAKEN = "taken"  # that Telegram account is someone's already, or the owner's configured one
ALREADY = "already"  # this person is connected already


@dataclass(frozen=True)
class Pending:
    expires_at: datetime
    claims: int


@dataclass(frozen=True)
class Status:
    connected: bool
    name: str | None
    since: datetime | None
    pending: Pending | None


@dataclass(frozen=True)
class Code:
    code: str  # to send to the claimer, once; only its hash is kept


@dataclass(frozen=True)
class Match:
    name: str  # the claimer's Telegram first name: a last check, never what's confirmed


@dataclass(frozen=True)
class Linked:
    chat: int  # to say "Connected" in


def _open(session: Session, now: datetime) -> TelegramLink | None:
    found: TelegramLink | None = session.scalar(
        select(TelegramLink)
        .where(TelegramLink.expires_at > now)
        .order_by(TelegramLink.id.desc())
        .limit(1)
    )
    return found


def _code_hash(link_id: int, code: str) -> str:
    return auth.hash_token(f"{link_id}:{code}")


def status(session: Session, user_id: int, now: datetime) -> Status:
    user = session.get(User, user_id)
    link = _open(session, now)
    return Status(
        connected=user is not None and user.telegram_user_id is not None,
        name=user.telegram_name if user is not None else None,
        since=user.telegram_linked_at if user is not None else None,
        pending=Pending(link.expires_at, len(link.claims)) if link is not None else None,
    )


def make(session: Session, now: datetime) -> str:
    """A new link's token for the person ``session`` is bound to, shown once. Any earlier link
    goes, with its claims: only the newest works."""
    session.execute(delete(TelegramLink))
    token = secrets.token_urlsafe(32)
    session.add(
        TelegramLink(token_hash=auth.hash_token(token), created_at=now, expires_at=now + LINK_TTL)
    )
    session.flush()
    log.info("telegram.link_made")
    return token


def cancel(session: Session) -> None:
    """End the bound person's link, if any, with its claims."""
    session.execute(delete(TelegramLink))


def clear_expired(session: Session, now: datetime) -> None:
    """Delete everyone's expired links, with the claims they held (``session`` unbound): on
    each claim, and daily with the wind-down, so a claimer's name and id don't stay."""
    session.execute(
        delete(TelegramLink).where(TelegramLink.expires_at <= now), execution_options=auth.EVERYONE
    )


def claim(
    session: Session,
    token: str,
    telegram_user_id: int,
    name: str,
    now: datetime,
    configured: int | None,
) -> Code | None:
    """The code for a sender who opened a link (``/start <token>``), or None when there's
    nothing to claim: an unknown, expired or full link, a link of someone connected already,
    or the owner's configured account (``configured``). The same sender again gets a new code
    in place of the old one. ``session`` is unbound: the token says whose link it is."""
    clear_expired(session, now)
    link = session.scalar(
        select(TelegramLink).where(TelegramLink.token_hash == auth.hash_token(token)),
        execution_options=auth.EVERYONE,
    )
    if link is None or telegram_user_id == configured:
        return None
    member = session.get(User, link.user_id)
    if member is None or member.telegram_user_id is not None:
        return None
    mine = next((c for c in link.claims if c.telegram_user_id == telegram_user_id), None)
    if mine is None and len(link.claims) >= MAX_CLAIMS:
        return None
    taken = {c.code_hash for c in link.claims if c is not mine}
    code = f"{secrets.randbelow(10**6):06d}"
    while _code_hash(link.id, code) in taken:  # a code names one claim: draw again
        code = f"{secrets.randbelow(10**6):06d}"
    if mine is None:
        mine = TelegramClaim(user_id=link.user_id, telegram_user_id=telegram_user_id)
        link.claims.append(mine)
    mine.name, mine.created_at = name[:NAME_LENGTH] or "?", now
    mine.code_hash = _code_hash(link.id, code)
    session.flush()
    log.info("telegram.claimed", claims=len(link.claims))
    return Code(code)


def _matching(session: Session, code: str, now: datetime) -> TelegramClaim | str:
    link = _open(session, now)
    if link is None:
        return NO_LINK
    if len(link.claims) > 1:
        return SHARED
    digest = _code_hash(link.id, code)
    found = next((c for c in link.claims if hmac.compare_digest(c.code_hash, digest)), None)
    if found is not None:
        return found
    link.wrong_codes += 1
    if link.wrong_codes >= MAX_WRONG:
        session.delete(link)
        log.info("telegram.link_ended")
        return ENDED
    return WRONG


def check(session: Session, code: str, now: datetime) -> Match | str:
    """The Telegram name a code was sent to, if it's the one claim's code on the bound person's
    link; otherwise why not. A wrong code counts towards the 5."""
    found = _matching(session, code, now)
    return Match(found.name) if isinstance(found, TelegramClaim) else found


def confirm(
    session: Session, user_id: int, code: str, now: datetime, configured: int | None
) -> Linked | str:
    """Connect ``user_id`` (``session`` is bound to them) to the Telegram account ``code`` was
    sent to; otherwise why not. One conditional update, so two at once can't both win. The
    link is used up, and the connecting is an event in their history."""
    found = _matching(session, code, now)
    if not isinstance(found, TelegramClaim):
        return found
    chat = found.telegram_user_id
    holder = session.scalar(select(User.id).where(User.telegram_user_id == chat))
    if chat == configured or holder is not None:
        return TAKEN
    done = session.execute(
        update(User)
        .where(User.id == user_id, User.telegram_user_id.is_(None))
        .values(telegram_user_id=chat, telegram_linked_at=now, telegram_name=found.name)
    )
    if cast("CursorResult[object]", done).rowcount != 1:
        return ALREADY
    session.execute(delete(TelegramLink))
    session.add(Event(kind=LINKED, payload={}, at=now))
    log.info("telegram.linked")
    return Linked(chat)


def unlink(session: Session, user_id: int, now: datetime) -> int | None:
    """Disconnect ``user_id``'s Telegram (``session`` is bound to them): the chat it was, to
    tell, or None if none was connected."""
    user = session.get(User, user_id)
    if user is None or user.telegram_user_id is None:
        return None
    chat = user.telegram_user_id
    user.telegram_user_id = user.telegram_linked_at = user.telegram_name = None
    session.add(Event(kind=UNLINKED, payload={}, at=now))
    log.info("telegram.unlinked")
    return chat
