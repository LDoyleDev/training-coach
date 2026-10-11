"""The secret a person's phone sends band data with (ADR-0055).

32 random bytes, shown once when made and stored only as their SHA-256. One per person: making
a new one replaces the old, removing it stops imports. Finding whose secret a request carries
is the question being asked, so that lookup runs in an unbound session with ``ALL_USERS``
(ADR-0029). The caller owns the transaction.
"""

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, IngestKey
from training_coach.db.session import ALL_USERS
from training_coach.services.auth import hash_token

PREFIX = "tci_"  # so a leaked one is recognisable as this app's
TOUCH_AFTER = timedelta(hours=1)  # last use is noted at most hourly: SQLite is on an SD card


@dataclass(frozen=True)
class Status:
    exists: bool
    created_at: datetime | None
    last_used_at: datetime | None


def status(session: Session) -> Status:
    row = session.scalar(select(IngestKey))
    if row is None:
        return Status(False, None, None)
    return Status(True, row.created_at, row.last_used_at)


def make(session: Session, now: datetime) -> str:
    """A new secret for the person ``session`` is bound to, replacing any earlier one."""
    secret = PREFIX + secrets.token_urlsafe(32)
    row = session.scalar(select(IngestKey))
    if row is None:
        session.add(IngestKey(key_hash=hash_token(secret), created_at=now))
    else:
        row.key_hash, row.created_at, row.last_used_at = hash_token(secret), now, None
    session.add(Event(kind="ingest.key_made", payload={}))
    session.flush()
    return secret


def remove(session: Session) -> bool:
    row = session.scalar(select(IngestKey))
    if row is None:
        return False
    session.delete(row)
    session.add(Event(kind="ingest.key_removed", payload={}))
    session.flush()
    return True


def owner_of(session: Session, secret: str, now: datetime) -> int | None:
    """Whose secret this is, in an unbound session; None for anything else."""
    if not secret.startswith(PREFIX) or len(secret) > 100:
        return None
    wanted = hash_token(secret)
    row = session.scalar(
        select(IngestKey).where(IngestKey.key_hash == wanted),
        execution_options={ALL_USERS: True},
    )
    if row is None or not hmac.compare_digest(row.key_hash, wanted):
        return None
    if row.last_used_at is None or now - row.last_used_at > TOUCH_AFTER:
        row.last_used_at = now
    return row.user_id
