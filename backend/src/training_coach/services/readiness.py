"""When the health questions were last answered (ADR-0085). The answers themselves never reach
the server: the browser asks, works out the note and keeps both on the device."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import ReadinessCheck
from training_coach.domain.readiness import VERSION, due


def latest(session: Session) -> ReadinessCheck | None:
    return session.scalar(select(ReadinessCheck))


def is_due(session: Session, now: datetime) -> bool:
    row = latest(session)
    return due(row.version if row else None, row.answered_at if row else None, now)


def answered(session: Session, now: datetime) -> ReadinessCheck:
    """Record that the current questions were answered now, replacing any earlier record."""
    row = latest(session)
    if row is None:
        row = ReadinessCheck()
        session.add(row)
    row.version, row.answered_at = VERSION, now
    session.flush()
    return row
