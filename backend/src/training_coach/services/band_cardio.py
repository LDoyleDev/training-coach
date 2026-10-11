"""Counting a workout from the band as cardio, after one tap (ADR-0054, ADR-0007).

A cardio workout from the band, at least 10 minutes and from the last 7 days, is offered on
Today and in Telegram until it is counted or turned down. Counting saves through the cardio
log (``services.cardio``): the planned session when it's today and today's plan is that kind
of cardio, an extra otherwise. The log token comes from the import's id, so counting twice,
from two places, saves once; /undo takes it back, after which it is offered again. The caller
owns the transaction and passes a session bound to the person.
"""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from training_coach.db.models import ImportedWorkout
from training_coach.domain import health
from training_coach.domain.enums import CardioActivity
from training_coach.services import cardio, workout_log

DAYS = 7  # offered for this many days, today included
MIN_MINUTES = 10


@dataclass(frozen=True)
class Offer:
    id: int
    on: date
    activity: CardioActivity
    minutes: int
    zone2: int | None  # minutes in zone 2; None without heart rate
    kind: str  # the cardio exercise it counts as: zone2 or moderate-cardio
    value: int  # the minutes it counts for
    text: str  # "Walk, 46 min, 38 in zone 2 - count it?"


@dataclass(frozen=True)
class Counted:
    workout_id: int
    already: bool  # it had been counted before: nothing changed
    planned: bool  # it completed today's planned session


@dataclass(frozen=True)
class Gone:
    """No such offer: never there, turned down, or too old."""


def token(import_id: int) -> str:
    """The cardio log's token for an import: the same one every time it is counted."""
    return hashlib.sha256(f"band-import:{import_id}".encode()).hexdigest()[:32]


def _zones(row: ImportedWorkout) -> list[int] | None:
    found = [row.zone1_min, row.zone2_min, row.zone3_min, row.zone4_min, row.zone5_min]
    return [m for m in found if m is not None] if None not in found else None


def _offer(row: ImportedWorkout) -> Offer | None:
    if row.activity is None:
        return None
    activity = CardioActivity(row.activity)
    zone_minutes = _zones(row)
    found = health.counted_as(activity, row.minutes, zone_minutes)
    if found is None:
        return None
    kind, value = found
    zone2 = zone_minutes[1] if zone_minutes is not None else None
    text = health.offer_text(activity, row.minutes, zone_minutes)
    return Offer(row.id, row.local_date, activity, row.minutes, zone2, kind, value, text)


def _open(today: date) -> list[ColumnElement[bool]]:
    return [
        ImportedWorkout.status != "dismissed",
        ImportedWorkout.workout_id.is_(None),  # undone: the workout is gone, so offer again
        ImportedWorkout.activity.is_not(None),
        ImportedWorkout.minutes >= MIN_MINUTES,
        ImportedWorkout.local_date > today - timedelta(days=DAYS),
        ImportedWorkout.local_date <= today,
    ]


def offers(session: Session, today: date) -> list[Offer]:
    """What to offer, oldest first."""
    rows = session.scalars(
        select(ImportedWorkout).where(*_open(today)).order_by(ImportedWorkout.start_at)
    )
    return [o for o in map(_offer, rows) if o is not None]


def unannounced(session: Session, today: date, now: datetime) -> list[Offer]:
    """Offers not yet sent to Telegram, marked as sent."""
    rows = list(
        session.scalars(
            select(ImportedWorkout)
            .where(*_open(today), ImportedWorkout.announced_at.is_(None))
            .order_by(ImportedWorkout.start_at)
        )
    )
    for row in rows:
        row.announced_at = now
    session.flush()
    return [o for o in map(_offer, rows) if o is not None]


def count(
    session: Session, import_id: int, today: date, tz: ZoneInfo
) -> Counted | Gone | workout_log.Stale:
    """Save an offer as cardio. Counting one already counted changes nothing."""
    row = session.get(ImportedWorkout, import_id)
    if row is None or row.status == "dismissed":
        return Gone()
    if row.workout_id is not None:
        return Counted(row.workout_id, already=True, planned=False)
    offer = _offer(row)
    if offer is None or offer.on <= today - timedelta(days=DAYS) or offer.on > today:
        return Gone()
    logged = cardio.log(
        session,
        offer.on,
        tz,
        offer.kind,
        offer.value,
        offer.activity,
        token(row.id),
        extra=offer.on != today,
    )
    if isinstance(logged, workout_log.Stale):
        return logged
    row.status, row.workout_id = "counted", logged.saved.workout_id
    session.flush()
    return Counted(logged.saved.workout_id, logged.saved.already_saved, logged.planned)


def dismiss(session: Session, import_id: int) -> bool:
    """Turn an offer down. False when there is no such workout."""
    row = session.get(ImportedWorkout, import_id)
    if row is None:
        return False
    if row.workout_id is None:
        row.status = "dismissed"
        session.flush()
    return True
