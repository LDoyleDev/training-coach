"""The secret a person's phone sends band data with (ADR-0055).

32 random bytes, shown once when made and stored only as their SHA-256. One per person: making
a new one replaces the old, removing it stops imports. Finding whose secret a request carries
is the question being asked, so that lookup runs in an unbound session with ``ALL_USERS``
(ADR-0029). The caller owns the transaction.

Each stored sync is noted, and so is the last one that took a record: the bot tells the person
when either stops for a day (``domain.band_watch``).
"""

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, IngestKey
from training_coach.db.session import ALL_USERS
from training_coach.domain import band_watch
from training_coach.domain.band_watch import Notice
from training_coach.services.auth import hash_token

PREFIX = "tci_"  # so a leaked one is recognisable as this app's
TOUCH_AFTER = timedelta(hours=1)  # syncs are noted at most hourly: SQLite is on an SD card


@dataclass(frozen=True)
class Status:
    exists: bool
    created_at: datetime | None
    last_used_at: datetime | None  # the last sync stored
    last_taken_at: datetime | None  # the last sync that took a record: data actually arrived


def status(session: Session) -> Status:
    row = session.scalar(select(IngestKey))
    if row is None:
        return Status(False, None, None, None)
    return Status(True, row.created_at, row.last_used_at, row.last_taken_at)


def make(session: Session, now: datetime) -> str:
    """A new secret for the person ``session`` is bound to, replacing any earlier one."""
    secret = PREFIX + secrets.token_urlsafe(32)
    row = session.scalar(select(IngestKey))
    if row is None:
        session.add(IngestKey(key_hash=hash_token(secret), created_at=now))
    else:
        row.key_hash, row.created_at = hash_token(secret), now
        row.last_used_at = row.last_taken_at = row.alerted_at = None  # the clock starts again
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


def owner_of(session: Session, secret: str) -> int | None:
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
    return row.user_id


def _due(noted: datetime | None, now: datetime) -> bool:
    return noted is None or now - noted > TOUCH_AFTER


def received(session: Session, now: datetime, took: bool) -> None:
    """Note a sync that was stored, and whether it took any record. Each is noted at most
    hourly, on its own clock: an empty sync noted a minute ago never hides one that took
    records. A refused sync (bad JSON, too large) is not noted."""
    row = session.scalar(select(IngestKey))
    if row is None:  # removed while the sync was being stored
        return
    if _due(row.last_used_at, now):
        row.last_used_at = now
    if took and _due(row.last_taken_at, now):
        row.last_taken_at = now


def watch(session: Session, now: datetime) -> Notice | None:
    """What to tell the person about their band data now; None without a secret."""
    row = session.scalar(select(IngestKey))
    if row is None:
        return None
    seen = band_watch.Seen(row.created_at, row.last_used_at, row.last_taken_at, row.alerted_at)
    return band_watch.notice(seen, now)


def told(session: Session, notice: Notice, now: datetime) -> None:
    """``notice`` reached the person: a gap is not told again until data flows again."""
    row = session.scalar(select(IngestKey))
    if row is not None:
        row.alerted_at = None if notice is Notice.BACK else now
