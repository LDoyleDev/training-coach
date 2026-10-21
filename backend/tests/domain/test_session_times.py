"""Which set times from the phone are kept (ADR-0061)."""

from datetime import UTC, datetime, timedelta

import pytest

from training_coach.domain.session_times import (
    BREAK,
    MAX_AGE,
    SLACK,
    SetTime,
    Timing,
    minutes,
    plausible,
    timing,
    usual,
)

NOW = datetime(2026, 10, 20, 18, 0, tzinfo=UTC)
SET = timedelta(seconds=40)


@pytest.mark.parametrize(
    ("started", "done", "kept"),
    [
        (NOW - SET, NOW, True),
        (NOW, NOW, True),  # confirmed straight away
        (NOW - SET, NOW + SLACK, True),  # a phone a minute ahead
        (NOW - MAX_AGE, NOW - MAX_AGE + SET, True),  # resumed the next morning
        (NOW, NOW - SET, False),  # ends before it starts
        (NOW, NOW + SLACK + timedelta(seconds=1), False),  # in the future
        (NOW - MAX_AGE - timedelta(seconds=1), NOW, False),  # too long ago
    ],
)
def test_set_times_are_kept_only_when_plausible(
    started: datetime, done: datetime, kept: bool
) -> None:
    assert plausible(started, done, NOW) is kept


def _set(start_min: float, seconds: int) -> SetTime:
    start = NOW + timedelta(minutes=start_min)
    return SetTime(start, start + timedelta(seconds=seconds))


def test_a_session_is_its_sets_and_the_rests_between_them() -> None:
    sets = [_set(2, 60), _set(0, 40), _set(4, 30)]  # in any order
    assert timing(sets) == Timing(
        total=timedelta(minutes=4, seconds=30),
        on_sets=timedelta(seconds=130),
        resting=timedelta(seconds=140),  # 80 s, then 60 s
        breaks=0,
        on_break=timedelta(),
    )


def test_a_long_gap_is_a_break_left_out_of_the_total() -> None:
    gap = BREAK + timedelta(minutes=5)
    sets = [_set(0, 60), _set(1 + gap / timedelta(minutes=1), 60)]
    found = timing(sets)
    assert found is not None
    assert (found.total, found.resting, found.breaks, found.on_break) == (
        timedelta(minutes=2),
        timedelta(),
        1,
        gap,
    )
    just = timing([_set(0, 60), _set(1 + BREAK / timedelta(minutes=1), 60)])
    assert just is not None
    assert (just.breaks, just.resting) == (0, BREAK)  # exactly BREAK is still a rest


def test_overlapping_sets_rest_nothing_and_no_times_is_no_timing() -> None:
    found = timing([_set(0, 120), _set(1, 30)])
    assert found is not None
    assert found.resting == timedelta()
    assert timing([]) is None


@pytest.mark.parametrize(
    ("span", "whole"),
    [
        (timedelta(), 0),
        (timedelta(seconds=10), 1),  # any time at all is at least a minute
        (timedelta(minutes=41, seconds=29), 41),
        (timedelta(minutes=41, seconds=31), 42),
    ],
)
def test_minutes_round_to_the_nearest(span: timedelta, whole: int) -> None:
    assert minutes(span) == whole


def test_the_usual_time_is_the_median_of_the_last_five() -> None:
    m = [timedelta(minutes=n) for n in (90, 40, 38, 45, 36, 41)]  # the 90 is too old to count
    assert usual(m) == timedelta(minutes=40)
    assert usual(m[-2:]) == timedelta(minutes=38, seconds=30)
    assert usual([]) is None
