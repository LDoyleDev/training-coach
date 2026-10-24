"""A cardio log's start, from the clock time typed (ADR-0067)."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from training_coach.domain.cardio import Details
from training_coach.services import cardio

BERLIN = ZoneInfo("Europe/Berlin")


def test_a_start_earlier_today_is_today() -> None:
    now = datetime(2026, 10, 23, 15, 30, tzinfo=UTC)  # 17:30 in Berlin
    found = cardio.started(date(2026, 10, 23), time(16, 26), BERLIN, now)
    assert found == datetime(2026, 10, 23, 14, 26, tzinfo=UTC)


def test_a_run_logged_after_midnight_started_yesterday() -> None:
    now = datetime(2026, 10, 23, 22, 15, tzinfo=UTC)  # 00:15 on the 24th in Berlin
    found = cardio.started(date(2026, 10, 24), time(23, 40), BERLIN, now)
    assert found == datetime(2026, 10, 23, 21, 40, tzinfo=UTC)
    assert found <= now


def test_a_start_the_spring_change_skips_never_happened() -> None:
    """Eval of 2026-10-24: 02:30 on 29 March was read as 03:30 and saved."""
    now = datetime(2026, 3, 29, 10, 0, tzinfo=UTC)
    assert cardio.started(date(2026, 3, 29), time(2, 30), BERLIN, now) is None
    found = cardio.started(date(2026, 3, 29), time(3, 30), BERLIN, now)
    assert found == datetime(2026, 3, 29, 1, 30, tzinfo=UTC)


def test_a_start_the_autumn_change_repeats_is_the_first() -> None:
    now = datetime(2026, 10, 25, 10, 0, tzinfo=UTC)
    found = cardio.started(date(2026, 10, 25), time(2, 30), BERLIN, now)
    assert found == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)  # 02:30 summer time


def test_minutes_from_the_start_must_end_by_now() -> None:
    """Eval of 2026-10-24: 17:50 plus 120 minutes was accepted at 18:00."""
    now = datetime(2026, 10, 23, 16, 0, tzinfo=UTC)
    began = Details(started_at=now - timedelta(minutes=10))
    assert cardio.problem("zone2", 120, began, now) == "start plus minutes can't be later than now"
    assert cardio.problem("zone2", 10, began, now) is None
    assert cardio.problem("hiit", 20, Details(started_at=now), now) is None  # rounds, not minutes
