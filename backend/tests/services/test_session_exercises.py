"""Exercises per session (ADR-0082 addendum): the trim keeps at most this many exercises of every
trimmable session, before the minutes, by the same drop key; a day's choice trims on top."""

from datetime import date
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.services.test_session_minutes import AS_PLANNED, _at, _choose, _sets, _today
from training_coach.db.models import Event
from training_coach.services import guided, user_settings
from training_coach.services.seed import apply_seed, load_plan

BERLIN = ZoneInfo("Europe/Berlin")
DAY = date(2026, 10, 12)


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def test_the_setting_is_stored_and_cleared_and_each_change_is_logged(session: Session) -> None:
    assert user_settings.load(session).session_exercises is None  # as planned for everyone
    assert user_settings.update(session, session_exercises=6).session_exercises == 6
    assert user_settings.update(session, session_minutes=30).session_exercises == 6  # kept
    assert user_settings.update(session, clear_session_exercises=True).session_exercises is None
    changes = [e.payload for e in session.scalars(select(Event).order_by(Event.id))]
    assert {"session_exercises": 6} in changes
    assert {"session_exercises": 0} in changes  # 0: back to as planned


def test_the_count_keeps_that_many_exercises_and_names_the_rest(plan: Session) -> None:
    user_settings.update(plan, session_exercises=4)
    found = _today(plan)
    assert sum(n > 0 for n in _sets(found)) == 4
    length = found.length
    assert length is not None
    assert len(length.trimmed.dropped) == 4  # named before Start, as the minutes' are
    assert length.minutes is None  # no minutes chosen: the sets stay as planned
    assert all(n in (0, planned) for n, planned in zip(_sets(found), AS_PLANNED, strict=True))
    assert length.planned < 49  # as planned is this person's four exercises


def test_a_session_with_the_count_or_fewer_is_as_planned(plan: Session) -> None:
    user_settings.update(plan, session_exercises=8)
    assert _sets(_today(plan)) == AS_PLANNED


def test_the_minutes_trim_what_the_count_leaves(plan: Session) -> None:
    user_settings.update(plan, session_exercises=6, session_minutes=20)
    found = _today(plan)
    assert sum(n > 0 for n in _sets(found)) <= 6
    assert found.minutes <= 20


def test_choosing_as_planned_for_the_day_keeps_the_count(plan: Session) -> None:
    """Short on time today trims on top: the day's As planned undoes the minutes, not the count."""
    user_settings.update(plan, session_exercises=4, session_minutes=20)
    found = _choose(plan, None)
    assert sum(n > 0 for n in _sets(found)) == 4


def test_a_recovery_session_keeps_every_exercise(plan: Session) -> None:
    user_settings.update(plan, session_exercises=4)
    _at(plan, "recovery")
    assert _today(plan).length is None
    assert guided.today(plan, DAY, BERLIN) is not None
