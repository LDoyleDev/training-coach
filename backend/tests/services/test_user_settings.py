from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, UserSettings, Workout
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import user_settings
from training_coach.services.user_settings import Prefs

DAY = date(2026, 10, 6)


def test_defaults_without_a_row(session: Session) -> None:
    assert user_settings.load(session) == Prefs()


def test_update_creates_the_row_and_logs_the_change(session: Session) -> None:
    prefs = user_settings.update(session, morning_time=time(6, 45), paused=True)
    assert prefs == Prefs(morning_time=time(6, 45), paused=True)
    session.flush()
    row = session.get(UserSettings, 1)
    assert row is not None
    assert (row.morning_time, row.paused) == (time(6, 45), True)
    payloads = session.scalars(select(Event.payload).where(Event.kind == "settings.changed"))
    assert list(payloads) == [{"morning_time": "06:45:00", "paused": True}]


def test_update_keeps_other_settings(session: Session) -> None:
    user_settings.update(session, nudge_time=time(21, 0))
    session.flush()
    prefs = user_settings.update(session, nudges_enabled=False)
    assert prefs == Prefs(nudge_time=time(21, 0), nudges_enabled=False)


def test_anything_logged_counts_every_status(session: Session) -> None:
    assert not user_settings.anything_logged(session, DAY)
    session.add(Workout(local_date=DAY, template_id=None, status=WorkoutStatus.SKIPPED))
    session.flush()
    assert user_settings.anything_logged(session, DAY)
    assert not user_settings.anything_logged(session, date(2026, 10, 7))


def test_no_event_when_nothing_changes(session: Session) -> None:
    user_settings.update(session, paused=True)
    user_settings.update(session, paused=True)
    session.flush()
    kinds = session.scalars(select(Event.kind).where(Event.kind == "settings.changed"))
    assert len(list(kinds)) == 1
