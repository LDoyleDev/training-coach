"""A cardio log's start, from the clock time typed (ADR-0067)."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

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
