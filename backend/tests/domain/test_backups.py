from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from training_coach.domain.backups import keep, next_run

BERLIN = ZoneInfo("Europe/Berlin")
AT = time(3, 30)


def days_back(start: date, count: int) -> list[date]:
    return [start - timedelta(days=n) for n in range(count)]


def test_keeps_everything_while_there_are_few_backups() -> None:
    days = days_back(date(2026, 10, 7), 5)
    assert keep(days) == set(days)


def test_keeps_nothing_when_there_is_nothing() -> None:
    assert keep([]) == set()


def test_keeps_seven_days_then_one_per_week_for_four_weeks() -> None:
    days = days_back(date(2026, 10, 7), 60)  # a Wednesday
    kept = keep(days)
    assert len(kept) == 11
    assert set(days[:7]) <= kept  # Oct 1-7
    weekly = sorted(kept - set(days[:7]), reverse=True)
    # The newest backup of each earlier ISO week; Oct 1 (Thursday) is already in the dailies,
    # so that week (Sep 28 - Oct 4) counts as covered.
    assert weekly == [date(2026, 9, 27), date(2026, 9, 20), date(2026, 9, 13), date(2026, 9, 6)]


def test_missed_nights_never_cost_a_kept_backup() -> None:
    """Counted over the backups that exist: after a week offline, the last seven are kept."""
    days = [date(2026, 10, 7), *days_back(date(2026, 9, 25), 20)]
    kept = keep(days)
    assert set(sorted(days, reverse=True)[:7]) <= kept
    assert date(2026, 10, 7) in kept


def test_duplicates_count_once() -> None:
    day = date(2026, 10, 7)
    assert keep([day, day]) == {day}


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        pytest.param(
            datetime(2026, 10, 7, 0, 0, tzinfo=UTC),
            datetime(2026, 10, 7, 1, 30, tzinfo=UTC),
            id="later-today",
        ),
        pytest.param(
            datetime(2026, 10, 7, 1, 30, tzinfo=UTC),
            datetime(2026, 10, 8, 1, 30, tzinfo=UTC),
            id="exactly-now-means-tomorrow",
        ),
        pytest.param(
            datetime(2026, 10, 7, 12, 0, tzinfo=UTC),
            datetime(2026, 10, 8, 1, 30, tzinfo=UTC),
            id="tomorrow",
        ),
        pytest.param(
            datetime(2026, 3, 28, 12, 0, tzinfo=UTC),
            datetime(2026, 3, 29, 1, 30, tzinfo=UTC),  # 03:30 CEST, after the spring jump
            id="spring-forward",
        ),
        pytest.param(
            datetime(2026, 10, 24, 12, 0, tzinfo=UTC),
            datetime(2026, 10, 25, 2, 30, tzinfo=UTC),  # 03:30 CET, after the clocks go back
            id="fall-back",
        ),
    ],
)
def test_next_run_is_the_next_local_half_three(now: datetime, expected: datetime) -> None:
    assert next_run(now, BERLIN, AT) == expected
    assert next_run(now, BERLIN, AT).astimezone(BERLIN).time() == AT
