"""Reading and changing the single settings row (times are local wall-clock, Europe/Berlin)."""

from dataclasses import dataclass
from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, UserSettings, Workout
from training_coach.services import users

DEFAULT_MORNING = time(7, 30)
DEFAULT_NUDGE = time(20, 0)


@dataclass(frozen=True)
class Prefs:
    morning_time: time = DEFAULT_MORNING
    nudge_time: time = DEFAULT_NUDGE
    nudges_enabled: bool = True
    paused: bool = False


def load(session: Session) -> Prefs:
    row = users.settings_row(session)
    if row is None:
        return Prefs()
    return Prefs(row.morning_time, row.nudge_time, row.nudges_enabled, row.paused)


def update(
    session: Session,
    *,
    morning_time: time | None = None,
    nudge_time: time | None = None,
    nudges_enabled: bool | None = None,
    paused: bool | None = None,
) -> Prefs:
    """Change the given settings (creating the row if needed) and log what changed."""
    old = load(session)
    prefs = Prefs(
        morning_time=old.morning_time if morning_time is None else morning_time,
        nudge_time=old.nudge_time if nudge_time is None else nudge_time,
        nudges_enabled=old.nudges_enabled if nudges_enabled is None else nudges_enabled,
        paused=old.paused if paused is None else paused,
    )
    changes: dict[str, str | bool] = {}
    if morning_time is not None:
        changes["morning_time"] = morning_time.isoformat()
    if nudge_time is not None:
        changes["nudge_time"] = nudge_time.isoformat()
    if nudges_enabled is not None:
        changes["nudges_enabled"] = nudges_enabled
    if paused is not None:
        changes["paused"] = paused
    row = users.settings_row(session)
    if row is None:
        row = UserSettings()
        session.add(row)
    row.morning_time = prefs.morning_time
    row.nudge_time = prefs.nudge_time
    row.nudges_enabled = prefs.nudges_enabled
    row.paused = prefs.paused
    if prefs != old:  # a repeated press changes nothing and logs nothing
        session.add(Event(kind="settings.changed", payload=changes))
    return prefs


def anything_logged(session: Session, on: date) -> bool:
    """Any workout on ``on``, whatever its status: done, rest or skipped (ADR-0014)."""
    return session.scalar(select(Workout.id).where(Workout.local_date == on).limit(1)) is not None
