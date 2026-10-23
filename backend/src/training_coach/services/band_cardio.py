"""Counting a workout from the band as cardio, after one tap (ADR-0055, ADR-0007).

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
from training_coach.domain.cardio import Details, details_problem
from training_coach.domain.enums import CardioActivity
from training_coach.services import cardio, workout_log
from training_coach.services.day_clash import Clash, Refused, Resolution

DAYS = 7  # offered for this many days, today included
ANNOUNCE_DAYS = 2  # sent to Telegram for this many days: today and yesterday
ANNOUNCE_AT_ONCE = 3  # at most this many each run; the rest go on the next one
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


def _details(row: ImportedWorkout) -> Details:
    """The band's heart rate and start for the log (ADR-0067); heart rate only when it makes
    sense, so an odd reading never stops the walk being counted."""
    found = Details(avg_hr=row.avg_hr, max_hr=row.max_hr, started_at=row.start_at)
    return (
        found if details_problem(found, rounds=False) is None else Details(started_at=row.start_at)
    )


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


def unannounced(session: Session, today: date) -> list[Offer]:
    """Offers not yet sent to Telegram, oldest first: from the last ``ANNOUNCE_DAYS`` days only
    (an older one stays on Today in the app), at most ``ANNOUNCE_AT_ONCE``, so the first run
    after a long gap doesn't send a week of them at once (review of #226). Nothing is marked;
    the caller marks each one once it is sent."""
    rows = session.scalars(
        select(ImportedWorkout)
        .where(
            *_open(today),
            ImportedWorkout.announced_at.is_(None),
            ImportedWorkout.local_date > today - timedelta(days=ANNOUNCE_DAYS),
        )
        .order_by(ImportedWorkout.start_at)
    )
    return [o for o in map(_offer, rows) if o is not None][:ANNOUNCE_AT_ONCE]


def announced(session: Session, import_id: int, now: datetime) -> None:
    """Mark an offer as sent to Telegram, so it isn't sent again."""
    row = session.get(ImportedWorkout, import_id)
    if row is not None:
        row.announced_at = now
        session.flush()


def count(
    session: Session, import_id: int, today: date, tz: ZoneInfo, answer: Resolution | None = None
) -> Counted | Gone | workout_log.Stale | Clash | Refused:
    """Save an offer as cardio. Counting one already counted changes nothing. When it would
    complete today's session on a day that already has one, it asks first (ADR-0060)."""
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
        answer=answer,
        details=_details(row),
    )
    if not isinstance(logged, cardio.Logged):
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
