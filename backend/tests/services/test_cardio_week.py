"""The Cardio card's running total: the last 7 days, not the calendar week (ADR-0077)."""

from datetime import date, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from training_coach.services import cardio, review
from training_coach.services.seed import apply_seed, load_plan

TZ = ZoneInfo("Europe/Berlin")
MONDAY = date(2026, 10, 26)


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _extra(session: Session, kind: str, minutes: int, on: date) -> None:
    logged = cardio.log(session, on, TZ, kind, minutes, None, uuid4().hex, extra=True)
    assert isinstance(logged, cardio.Logged)
    session.flush()


def test_the_last_seven_days_are_today_and_the_six_before() -> None:
    assert review.last_days(MONDAY) == MONDAY - timedelta(days=6)
    assert review.last_days(MONDAY, 1) == MONDAY


def test_on_a_monday_the_weekend_still_counts(plan: Session) -> None:
    """Owner, 26 Oct 2026: Saturday's cardio vanished from "this week" on Monday."""
    _extra(plan, cardio.ZONE2, 50, MONDAY - timedelta(days=2))  # Saturday
    _extra(plan, cardio.MODERATE, 25, MONDAY - timedelta(days=6))  # the oldest of the 7 days
    _extra(plan, cardio.ZONE2, 40, MONDAY - timedelta(days=7))  # a week ago: outside
    _extra(plan, cardio.ZONE2, 30, MONDAY - timedelta(days=8))
    week = cardio.week(plan, MONDAY)
    assert (week.zone2, week.moderate, week.zone2_target) == (50, 25, (180, 200))


def test_the_weekly_review_still_starts_on_monday(plan: Session) -> None:
    _extra(plan, cardio.ZONE2, 50, MONDAY - timedelta(days=2))
    found = review.weekly(plan, MONDAY, TZ)
    assert (found.start, found.zone2_minutes, found.extras) == (MONDAY, 0, 0)
