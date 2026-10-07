from datetime import date, timedelta

import pytest

from training_coach.domain.habits import HINTS, LABELS, Habit, HabitWeek, can_change, tally

MONDAY = date(2026, 10, 5)
M, P, W = Habit.MORNING_LIGHT, Habit.PROTEIN, Habit.WIND_DOWN


def day(n: int) -> date:
    return MONDAY + timedelta(days=n)


def test_every_habit_has_a_label_and_a_hint() -> None:
    assert set(LABELS) == set(HINTS) == set(Habit)


@pytest.mark.parametrize(
    ("ago", "allowed"), [(-1, False), (0, True), (1, True), (2, True), (3, False)]
)
def test_a_check_off_can_change_for_today_and_two_days_back(ago: int, allowed: bool) -> None:
    assert can_change(day(3) - timedelta(days=ago), day(3)) is allowed


def test_a_full_week_counts_days_done_out_of_seven() -> None:
    checked = [(day(n), M) for n in range(5)] + [(day(0), P), (day(6), W)]
    assert tally(checked, MONDAY, day(6)) == [
        HabitWeek(M, 5, 7),
        HabitWeek(P, 1, 7),
        HabitWeek(W, 1, 7),
    ]


def test_mid_week_counts_only_the_days_so_far() -> None:
    checked = [(day(0), M), (day(2), M), (day(5), M)]  # day 5 is after "on": not yet
    assert tally(checked, MONDAY, day(2))[0] == HabitWeek(M, 2, 3)


def test_days_outside_the_week_and_repeats_are_ignored() -> None:
    checked = [(day(-1), M), (day(7), M), (day(1), M), (day(1), M)]
    assert tally(checked, MONDAY, day(6))[0] == HabitWeek(M, 1, 7)


def test_a_later_day_still_counts_a_week_of_seven() -> None:
    assert tally([], MONDAY, day(20))[0].days == 7
