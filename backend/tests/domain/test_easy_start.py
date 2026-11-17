"""The easy start (ADR-0094): a light start of the later of 4 sessions and 14 days, then one set
lower for the later of 8 sessions and 28 days, counted from the first workout."""

from datetime import date, timedelta

import pytest

from training_coach.domain.easy_start import (
    MOST_EXTRA_WEEKS,
    Phase,
    Setting,
    extended,
    holds_move_up,
    minutes,
    notice,
    restarted,
    sets,
    state,
    target,
)

START = date(2026, 12, 1)
ON = Setting(True)


def day(n: int) -> date:
    return START + timedelta(days=n)


def days(*ns: int) -> list[date]:
    return [day(n) for n in ns]


# a 3-day person: Mon, Wed, Fri
THREE_A_WEEK = days(0, 2, 4, 7, 9, 11, 14, 16, 18, 21, 23, 25, 28, 30, 32, 35, 37, 39, 42, 44, 46)


def test_off_is_off_whatever_was_logged() -> None:
    assert state(Setting(False), THREE_A_WEEK, day(5)).phase is Phase.OFF


def test_on_with_nothing_logged_waits_for_the_first_workout() -> None:
    assert state(ON, [], day(30)).phase is Phase.WAITING


def test_the_first_workouts_day_is_still_waiting_while_it_is_logged() -> None:
    assert state(ON, days(0), day(0)).phase is Phase.WAITING


def test_workouts_before_since_dont_count() -> None:
    setting = Setting(True, since=day(10))
    assert state(setting, days(0, 2, 4), day(11)).phase is Phase.WAITING
    assert state(setting, days(0, 2, 4, 10), day(11)).count == 1


def test_the_light_start_counts_sessions_before_the_day() -> None:
    now = state(ON, THREE_A_WEEK, day(5))
    assert (now.phase, now.count, now.of, now.until) == (Phase.LIGHT, 3, 4, day(14))
    assert now.over_from == day(14 + 28)
    assert not now.ending
    assert not now.restart
    assert now.extend is None


def test_four_sessions_early_still_run_to_day_14() -> None:
    assert state(ON, THREE_A_WEEK, day(13)).phase is Phase.LIGHT
    lower = state(ON, THREE_A_WEEK, day(14))
    assert (lower.phase, lower.count, lower.fresh) == (Phase.LOWER, 0, True)


def test_a_slow_start_runs_until_the_fourth_session() -> None:
    weekly = days(0, 7, 14, 21, 28)
    before = state(ON, weekly, day(20))
    assert (before.phase, before.count, before.ending) == (Phase.LIGHT, 3, True)
    assert before.over_from == day(21 + 28)
    assert state(ON, weekly, day(21)).phase is Phase.LIGHT  # the 4th is today's
    assert state(ON, weekly, day(22)).phase is Phase.LOWER


def test_two_workouts_on_one_day_count_twice() -> None:
    assert state(ON, days(0, 0, 1, 1), day(15)).phase is Phase.LOWER


def test_one_set_lower_runs_the_later_of_8_sessions_and_28_days() -> None:
    now = state(ON, THREE_A_WEEK, day(20))
    assert (now.phase, now.count, now.of, now.until) == (Phase.LOWER, 3, 8, day(42))
    assert now.over_from == day(42)
    assert not now.fresh
    assert not now.ending
    assert state(ON, THREE_A_WEEK, day(41)).ending
    done = state(ON, THREE_A_WEEK, day(42))
    assert (done.phase, done.fresh, done.over_from) == (Phase.DONE, True, day(42))
    assert not state(ON, THREE_A_WEEK, day(43)).fresh


def test_too_few_sessions_keep_one_set_lower_going() -> None:
    sparse = days(0, 2, 4, 7, 20, 40)
    assert state(ON, sparse, day(60)).phase is Phase.LOWER


def test_a_gap_of_14_days_offers_a_restart() -> None:
    assert not state(ON, days(0, 2), day(15)).restart
    assert state(ON, days(0, 2), day(16)).restart
    assert state(ON, days(0, 2, 4, 7, 9), day(30)).restart  # one set lower
    fresh = restarted(day(30))
    assert fresh == Setting(True, day(30))
    assert state(fresh, days(0, 2, 4, 7, 9), day(31)).phase is Phase.WAITING


def test_one_more_easy_week_brings_the_light_start_back() -> None:
    lower = state(ON, THREE_A_WEEK, day(15))
    assert lower.extend is Phase.LIGHT
    longer = extended(ON, Phase.LIGHT)
    again = state(longer, THREE_A_WEEK, day(15))
    assert (again.phase, again.until) == (Phase.LIGHT, day(21))
    assert state(ON, THREE_A_WEEK, day(21)).extend is None  # 7 days on: no longer offered


def test_one_more_easy_week_brings_one_set_lower_back() -> None:
    done = state(ON, THREE_A_WEEK, day(43))
    assert done.extend is Phase.LOWER
    longer = extended(ON, Phase.LOWER)
    assert state(longer, THREE_A_WEEK, day(43)).phase is Phase.LOWER
    assert state(longer, THREE_A_WEEK, day(49)).phase is Phase.DONE
    assert state(ON, THREE_A_WEEK, day(49)).extend is None


def test_at_most_two_easy_weeks() -> None:
    used = Setting(True, weeks_light=1, weeks_lower=MOST_EXTRA_WEEKS - 1)
    assert state(used, THREE_A_WEEK, day(57)).phase is Phase.DONE
    assert state(used, THREE_A_WEEK, day(57)).extend is None
    assert state(Setting(True, weeks_light=2), THREE_A_WEEK, day(29)).extend is None
    with pytest.raises(ValueError, match="no easy week left"):
        extended(used, Phase.LOWER)


@pytest.mark.parametrize("phase", [Phase.OFF, Phase.WAITING, Phase.DONE])
def test_only_the_two_phases_can_be_extended(phase: Phase) -> None:
    with pytest.raises(ValueError, match="can't be extended"):
        extended(ON, phase)


@pytest.mark.parametrize(
    ("phase", "planned", "expected"),
    [
        pytest.param(Phase.WAITING, 3, 1, id="first-day-one"),
        pytest.param(Phase.LIGHT, 4, 1, id="light-one"),
        pytest.param(Phase.LOWER, 3, 2, id="lower-one-fewer"),
        pytest.param(Phase.LOWER, 1, 1, id="lower-a-single-set-stays"),
        pytest.param(Phase.DONE, 3, 3, id="done-as-planned"),
        pytest.param(Phase.OFF, 4, 4, id="off-as-planned"),
    ],
)
def test_sets(phase: Phase, planned: int, expected: int) -> None:
    assert sets(phase, planned) == expected


@pytest.mark.parametrize(
    ("phase", "planned", "expected"),
    [
        pytest.param(Phase.LIGHT, 30, 10, id="light-at-most-10"),
        pytest.param(Phase.WAITING, 8, 8, id="shorter-stays"),
        pytest.param(Phase.LIGHT, None, None, id="not-timed"),
        pytest.param(Phase.LOWER, 30, 30, id="lower-as-planned"),
    ],
)
def test_minutes(phase: Phase, planned: int | None, expected: int | None) -> None:
    assert minutes(phase, planned) == expected


def test_targets_cap_at_the_bottom_of_the_range_in_the_light_start() -> None:
    assert target(Phase.LIGHT, 12, 8) == 8
    assert target(Phase.WAITING, 6, 8) == 6
    assert target(Phase.LOWER, 12, 8) == 12


def test_move_up_waits_in_the_light_start_only() -> None:
    assert [holds_move_up(p) for p in Phase] == [False, True, True, False, False]


@pytest.mark.parametrize(
    ("phase", "told", "expected"),
    [
        pytest.param(Phase.LIGHT, None, None, id="light-none"),
        pytest.param(Phase.LOWER, None, Phase.LOWER, id="lower-due"),
        pytest.param(Phase.LOWER, Phase.LIGHT, Phase.LOWER, id="lower-after-light"),
        pytest.param(Phase.LOWER, Phase.LOWER, None, id="lower-told"),
        pytest.param(Phase.DONE, Phase.LOWER, Phase.DONE, id="done-due"),
        pytest.param(Phase.LOWER, Phase.DONE, None, id="back-after-an-easy-week"),
    ],
)
def test_each_notice_once(phase: Phase, told: Phase | None, expected: Phase | None) -> None:
    assert notice(phase, told) is expected
