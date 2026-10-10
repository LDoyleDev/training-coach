"""A person's own Groq key for AI comments (ADR-0047 B): stored encrypted, shown only by its
last four characters, with an on/off and which health data the comments may see.

The key is checked with Groq before it is stored. The caller owns the transaction.
"""

from dataclasses import dataclass
from datetime import datetime

from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import AiConnection, Event
from training_coach.db.session import ALL_USERS
from training_coach.services.secret_box import SecretBox


@dataclass(frozen=True)
class Status:
    connected: bool
    ends_in: str | None
    enabled: bool
    body: bool
    readiness: bool
    failed: bool


NONE = Status(False, None, False, False, False, False)


def _row(session: Session) -> AiConnection | None:
    return session.scalar(select(AiConnection))


def status(session: Session) -> Status:
    row = _row(session)
    if row is None:
        return NONE
    return Status(
        True,
        row.key_ends,
        row.enabled,
        row.share_body,
        row.share_readiness,
        row.failed_at is not None,
    )


def store(session: Session, box: SecretBox, key: SecretStr) -> None:
    """Keep ``key`` (already checked with Groq), replacing any earlier one. Comments go on."""
    plain = key.get_secret_value()
    row = _row(session)
    if row is None:
        row = AiConnection(groq_key=box.seal(plain), key_ends=plain[-4:])
        session.add(row)
    else:
        row.groq_key = box.seal(plain)
        row.key_ends = plain[-4:]
    row.enabled = True
    row.failed_at = None
    session.add(Event(kind="ai.key_stored", payload={}))


def remove(session: Session) -> bool:
    row = _row(session)
    if row is None:
        return False
    session.delete(row)
    session.add(Event(kind="ai.key_removed", payload={}))
    return True


def options(session: Session, *, enabled: bool, body: bool, readiness: bool) -> bool:
    """Turn comments on or off and choose the health data they see. False with no key."""
    row = _row(session)
    if row is None:
        return False
    row.enabled, row.share_body, row.share_readiness = enabled, body, readiness
    return True


def key(session: Session, box: SecretBox, now: datetime) -> SecretStr | None:
    """The stored key, or None when there is none or it can't be opened (a lost secrets key:
    marked failed, so the person is asked to enter it again)."""
    row = _row(session)
    if row is None:
        return None
    opened = box.open(row.groq_key)
    if opened is None:
        failed(session, now)
    return opened


def failed(session: Session, at: datetime) -> bool:
    """Mark the key as failing. True only the first time, so the person is told once."""
    row = _row(session)
    if row is None or row.failed_at is not None:
        return False
    row.failed_at = at
    return True


def rotate_all(session: Session, box: SecretBox) -> tuple[int, int]:
    """Re-seal every stored key with the newest secrets key (an unbound session: a system task
    over everyone). Returns (re-sealed, unreadable)."""
    rows = session.scalars(select(AiConnection).execution_options(**{ALL_USERS: True}))
    done = lost = 0
    for row in rows:
        sealed = box.rotate(row.groq_key)
        if sealed is None:
            lost += 1
        else:
            row.groq_key = sealed
            done += 1
    return done, lost
