"""Test days in the schedule (#95, ADR-0038): today, the week ahead and blocks."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from training_coach.db.models import FitnessTestDay
from training_coach.services import users
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.today import today, week

TZ = ZoneInfo("Europe/Berlin")
DAY = date(2026, 10, 6)


@pytest.fixture
def seeded(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _tested(session: Session, on: date, day: int) -> None:
    session.add(
        FitnessTestDay(
            local_date=on,
            day=day,
            time_of_day="morning",
            fed=True,
            slept_well=True,
            results=[],
            token=f"t-{on}-{day}".ljust(20, "x"),
        )
    )
    session.flush()


def _first_session(session: Session) -> str:
    plan = today(session, DAY)
    assert plan is not None
    return plan.session.name


def test_nothing_is_due_before_the_baseline_is_started(seeded: Session) -> None:
    plan = today(seeded, DAY, TZ)
    assert plan is not None
    assert plan.test_day is None
    days = week(seeded, DAY, tz=TZ)
    assert days is not None
    assert all("test" not in d.session.lower() for d in days)


def test_day_2_of_the_baseline_comes_the_day_after_day_1(seeded: Session) -> None:
    _tested(seeded, DAY - timedelta(days=1), 1)
    plan = today(seeded, DAY, TZ)
    assert plan is not None
    assert plan.test_day is not None
    assert (plan.test_day.day, plan.test_day.name) == (2, "Baseline tests, day 2")
    assert "Bulgarian split squat" in plan.test_day.tests
    assert plan.session.name == _first_session(seeded)  # the session waits


def test_the_week_puts_the_test_day_first_and_shifts_the_sessions(seeded: Session) -> None:
    plain = week(seeded, DAY, days=3, tz=TZ)
    _tested(seeded, DAY - timedelta(days=1), 1)
    shifted = week(seeded, DAY, days=3, tz=TZ)
    assert plain is not None
    assert shifted is not None
    assert shifted[0].session == "Baseline tests, day 2"
    assert [d.session for d in shifted[1:]] == [d.session for d in plain[:2]]
    assert [d.date for d in shifted] == [d.date for d in plain]


def test_a_retest_falls_due_four_weeks_after_the_last_day_1(seeded: Session) -> None:
    _tested(seeded, DAY, 1)
    _tested(seeded, DAY + timedelta(days=1), 2)
    days = week(seeded, DAY + timedelta(days=25), tz=TZ)
    assert days is not None
    named = {d.date: d.session for d in days}
    assert named[DAY + timedelta(days=28)] == "Retest, day 1"
    assert named[DAY + timedelta(days=29)] == "Retest, day 2"


def test_a_test_day_saved_today_starts_the_week_tomorrow(seeded: Session) -> None:
    _tested(seeded, DAY, 1)
    plan = today(seeded, DAY, TZ)
    assert plan is not None
    assert plan.test_day is None  # day 2 is never the same day
    days = week(seeded, DAY, days=2, tz=TZ)
    assert days is not None
    assert [(d.date, d.session) for d in days] == [
        (DAY + timedelta(days=1), "Baseline tests, day 2"),
        (DAY + timedelta(days=2), _first_session(seeded)),
    ]


def test_with_blocks_on_each_block_start_brings_a_retest(seeded: Session) -> None:
    started = DAY - timedelta(days=28)
    _tested(seeded, started, 1)
    _tested(seeded, started + timedelta(days=1), 2)
    row = users.settings_row(seeded)
    assert row is not None
    row.blocks_started_on = started
    seeded.flush()
    plan = today(seeded, DAY, TZ)  # the second block starts today
    assert plan is not None
    assert plan.test_day is not None
    assert plan.test_day.name == "Retest, day 1"
    middle = today(seeded, started + timedelta(days=10), TZ)
    assert middle is not None
    assert middle.test_day is None


def test_without_a_time_zone_there_is_no_test_day(seeded: Session) -> None:
    """Callers that don't know the time zone can't place blocks, so they get the session."""
    _tested(seeded, DAY - timedelta(days=1), 1)
    plan = today(seeded, DAY)
    assert plan is not None
    assert plan.test_day is None
