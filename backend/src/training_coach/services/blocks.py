"""Which training block a day is in (ADR-0028), from the settings and the pause history."""

from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event
from training_coach.domain.blocks import Block, block_on, paused_days
from training_coach.services import users


def current(session: Session, on: date, tz: ZoneInfo) -> Block | None:
    """The block ``on`` falls in, or None when blocks are off."""
    row = users.settings_row(session)
    if row is None or row.blocks_started_on is None:
        return None
    changes = [
        (event.at.astimezone(tz).date(), bool(event.payload["paused"]))
        for event in session.scalars(
            select(Event).where(Event.kind == "settings.changed").order_by(Event.at, Event.id)
        )
        if isinstance(event.payload, dict) and isinstance(event.payload.get("paused"), bool)
    ]
    return block_on(on, row.blocks_started_on, paused_days(changes, until=on))
