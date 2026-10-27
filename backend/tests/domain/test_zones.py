from datetime import UTC, datetime, timedelta

import pytest

from training_coach.domain import zones
from training_coach.domain.zones import Zones

T = datetime(2026, 10, 10, 15, 0, tzinfo=UTC)


def test_karvonen_counts_from_the_heart_rate_reserve() -> None:
    found = zones.karvonen(50, 190)  # reserve 140
    assert found == Zones(50, 190, ((120, 134), (134, 148), (148, 162), (162, 176), (176, 190)))


def test_a_max_at_or_below_rest_still_makes_zones() -> None:
    assert zones.karvonen(60, 55).max == 61


@pytest.mark.parametrize(
    ("bpm", "zone"),
    [(90, 0), (119.6, 0), (120, 1), (133, 1), (134, 2), (147, 2), (148, 3), (176, 5), (205, 5)],
)
def test_the_zone_of_a_heart_rate(bpm: float, zone: int) -> None:
    assert zones.karvonen(50, 190).zone(bpm) == zone


def test_max_estimated_from_age() -> None:
    assert zones.estimated_max(40) == 180
    assert zones.estimated_max(25) == 190  # 190.5 rounds to even


def test_age_needs_a_believable_birth_year() -> None:
    assert zones.age(1986, 2026) == 40
    assert zones.age(None, 2026) is None
    assert zones.age(2020, 2026) is None
    assert zones.age(1900, 2026) is None


def test_their_own_max_wins_then_the_higher_of_estimate_and_peak() -> None:
    assert zones.max_heart_rate(own=175, years=40, peak=195) == 175
    assert zones.max_heart_rate(own=None, years=40, peak=None) == 180
    assert zones.max_heart_rate(own=None, years=40, peak=186) == 186  # a workout went higher
    assert zones.max_heart_rate(own=None, years=40, peak=170) == 180
    assert zones.max_heart_rate(own=None, years=None, peak=170) == zones.DEFAULT_MAX
    assert zones.max_heart_rate(own=None, years=None, peak=196) == 196
    assert zones.max_heart_rate(own=None, years=None, peak=None) == zones.DEFAULT_MAX


def _minutes(*rates: float, start: datetime = T) -> list[tuple[datetime, float]]:
    return [(start + timedelta(minutes=n), bpm) for n, bpm in enumerate(rates)]


def test_a_peak_counts_only_as_held_for_three_minutes() -> None:
    # Security test, 2026-10-24: one 230 reading moved max heart rate and every zone.
    assert zones.sustained(_minutes(150, 230, 150, 150)) == 150
    assert zones.sustained(_minutes(150, 181, 182.4, 190, 150)) == 181
    gap = _minutes(195, 195) + _minutes(195, start=T + timedelta(minutes=5))
    assert zones.sustained(gap) is None  # not three minutes in a row
    assert zones.sustained(_minutes(200, 200)) is None


def test_a_peak_raises_the_estimate_by_at_most_twenty() -> None:
    assert zones.counted_peak(None, 230) == zones.DEFAULT_MAX + zones.RAISE_LIMIT
    assert zones.counted_peak(40, 195) == 195  # an estimate of 180
    assert zones.counted_peak(40, 215) == 200
    assert zones.counted_peak(40, None) is None


def test_resting_is_the_median_of_the_last_seven_nights() -> None:
    assert zones.resting([50, 52, 48, 70, 51, 49, 50, 90, 90]) == 50  # the 90s are too old
    assert zones.resting([50, 53]) == 52  # 51.5 rounds to even
    assert zones.resting([]) == zones.DEFAULT_REST


def test_minutes_in_each_zone() -> None:
    hr = zones.karvonen(50, 190)
    readings = [(T + timedelta(minutes=n), 140) for n in range(38)]
    readings = [(T - timedelta(minutes=8 - n), 100) for n in range(8)] + readings
    assert zones.minutes(readings, T + timedelta(minutes=38), hr) == [0, 38, 0, 0, 0]


def test_a_gap_counts_at_most_five_minutes_and_the_last_reading_runs_to_the_end() -> None:
    hr = zones.karvonen(50, 190)
    readings = [(T, 125), (T + timedelta(minutes=30), 165)]
    assert zones.minutes(readings, T + timedelta(minutes=31), hr) == [5, 0, 0, 1, 0]
    assert zones.minutes([(T, 125)], T - timedelta(minutes=1), hr) == [0, 0, 0, 0, 0]
    assert zones.minutes([], T, hr) == [0, 0, 0, 0, 0]


def test_measured_counts_the_minutes_below_zone_1_too() -> None:
    hr = zones.karvonen(60, 180)  # zone 1 from 120
    readings = [(T + timedelta(minutes=n), 100 if n < 10 else 140) for n in range(40)]
    assert zones.measured(readings, T + timedelta(minutes=40), hr) == [10, 0, 30, 0, 0, 0]


def test_a_split_fills_the_rest_by_the_kind_logged() -> None:
    found = zones.split(66, harder=False, found=[20, 5, 35, 4, 0, 0])
    assert (found.total, found.zone2, found.zone2_unmeasured) == (66, 37, 2)  # 2 min unread
    run = zones.split(43, harder=True)  # a typed run: no heart rate
    assert (run.total, run.zone2, run.harder_unmeasured, run.measured) == (43, 0, 43, (0,) * 6)
    walk = zones.split(30, harder=False)
    assert (walk.zone2, walk.zone2_unmeasured, walk.harder_unmeasured) == (30, 30, 0)


def test_a_split_trims_rounding_from_the_largest_zones() -> None:
    assert zones.split(10, False, [6, 0, 6, 0, 0, 0]).measured == (4, 0, 6, 0, 0, 0)
    assert zones.split(5, False, [4, 0, 4, 0, 0, 0]).measured == (1, 0, 4, 0, 0, 0)
    assert zones.split(0, True, [1, 1, 0, 0, 0, 0]).total == 0


def test_splits_add_up() -> None:
    week = zones.split(66, False, [20, 7, 35, 4, 0, 0]) + zones.split(43, True)
    assert (week.total, week.zone2, week.harder_unmeasured) == (109, 35, 43)
    assert week.measured == (20, 7, 35, 4, 0, 0)
    assert zones.Split().total == 0
