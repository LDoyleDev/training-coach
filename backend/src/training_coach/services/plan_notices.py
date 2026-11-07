"""What a release changed in a person's plan (ADR-0087): shown until they've seen it, and told on
Telegram once. The seed writes these; nothing here changes the plan."""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import PlanNotice


def unread(session: Session) -> list[PlanNotice]:
    return list(
        session.scalars(
            select(PlanNotice).where(PlanNotice.read_at.is_(None)).order_by(PlanNotice.id)
        )
    )


def mark_read(session: Session, ids: Sequence[int], now: datetime) -> None:
    """Mark these as seen. The binding means another person's id finds nothing."""
    for notice in session.scalars(select(PlanNotice).where(PlanNotice.id.in_(ids))):
        if notice.read_at is None:
            notice.read_at = now


def untold(session: Session) -> list[PlanNotice]:
    """Those not yet sent to Telegram, and not already seen in the app."""
    return [notice for notice in unread(session) if notice.told_at is None]


def mark_told(session: Session, ids: Sequence[int], now: datetime) -> None:
    for notice in session.scalars(select(PlanNotice).where(PlanNotice.id.in_(ids))):
        notice.told_at = now
