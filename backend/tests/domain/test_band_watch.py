"""When band data counts as stopped, and when to say so (ADR-0055)."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from training_coach.domain.band_watch import Notice, Seen, daytime, notice

MADE = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
NOW = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)
DAY = timedelta(hours=24)
BERLIN = ZoneInfo("Europe/Berlin")


def _seen(
    used: timedelta | None, taken: timedelta | None, alerted: timedelta | None = None
) -> Seen:
    """Times as how long before NOW."""
    return Seen(
        MADE,
        None if used is None else NOW - used,
        None if taken is None else NOW - taken,
        None if alerted is None else NOW - alerted,
    )


@pytest.mark.parametrize(
    ("seen", "expected"),
    [
        (_seen(timedelta(hours=1), timedelta(hours=1)), None),
        (_seen(DAY + timedelta(minutes=1), DAY + timedelta(minutes=1)), Notice.QUIET),
        (_seen(None, None), Notice.QUIET),  # made long ago, never used
        (_seen(timedelta(hours=1), DAY + timedelta(minutes=1)), Notice.EMPTY),
        (_seen(timedelta(hours=1), None), Notice.EMPTY),  # syncs, never a record
        (_seen(DAY, DAY), None),  # exactly a day is not yet more than a day
    ],
    ids=["flowing", "quiet", "never", "empty", "never-taken", "just-a-day"],
)
def test_a_gap_is_quiet_or_empty(seen: Seen, expected: Notice | None) -> None:
    assert notice(seen, NOW) is expected


def test_a_new_secret_starts_the_clock() -> None:
    fresh = Seen(NOW - timedelta(hours=23), None, None, None)
    assert notice(fresh, NOW) is None
    assert notice(fresh, NOW + timedelta(hours=2)) is Notice.QUIET


def test_a_told_gap_isnt_told_again() -> None:
    assert notice(_seen(DAY * 3, DAY * 3, alerted=DAY * 2), NOW) is None
    assert notice(_seen(timedelta(hours=1), DAY * 3, alerted=DAY), NOW) is None  # still empty


def test_records_after_the_alert_mean_data_is_back() -> None:
    assert notice(_seen(timedelta(hours=1), timedelta(hours=1), alerted=DAY), NOW) is Notice.BACK


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        # Summer time (UTC+2): 05:59 UTC is 07:59 in Berlin, 06:00 is 08:00.
        (datetime(2026, 3, 29, 5, 59, tzinfo=UTC), False),
        (datetime(2026, 3, 29, 6, 0, tzinfo=UTC), True),
        (datetime(2026, 3, 29, 18, 59, tzinfo=UTC), True),
        (datetime(2026, 3, 29, 19, 0, tzinfo=UTC), False),
        # Winter time (UTC+1), the day the clocks go back: 07:00 UTC is 08:00 in Berlin.
        (datetime(2026, 10, 25, 6, 59, tzinfo=UTC), False),
        (datetime(2026, 10, 25, 7, 0, tzinfo=UTC), True),
        (datetime(2026, 10, 25, 19, 59, tzinfo=UTC), True),
        (datetime(2026, 10, 25, 20, 0, tzinfo=UTC), False),
        # Through the night the clocks change on, held either way.
        (datetime(2026, 3, 29, 1, 30, tzinfo=UTC), False),
        (datetime(2026, 10, 25, 1, 30, tzinfo=UTC), False),
    ],
)
def test_messages_wait_for_the_local_day_across_dst(moment: datetime, expected: bool) -> None:
    assert daytime(moment, BERLIN) is expected
