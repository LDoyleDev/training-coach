"""Habit check-offs (#90): ticking, unticking and the week's tally."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import HabitCheck
from training_coach.domain.habits import Habit, HabitWeek
from training_coach.services import habits

MONDAY = date(2026, 10, 5)
M, P = Habit.MORNING_LIGHT, Habit.PROTEIN


def test_a_tap_ticks_and_a_second_tap_unticks(session: Session) -> None:
    assert habits.toggle(session, MONDAY, M, MONDAY) is True
    assert habits.checked(session, MONDAY) == {M}
    assert habits.toggle(session, MONDAY, M, MONDAY) is False
    assert habits.checked(session, MONDAY) == frozenset()
    assert session.scalar(select(func.count()).select_from(HabitCheck)) == 0


def test_days_are_kept_apart(session: Session) -> None:
    habits.toggle(session, MONDAY, M, MONDAY + timedelta(days=1))
    habits.toggle(session, MONDAY + timedelta(days=1), P, MONDAY + timedelta(days=1))
    assert habits.checked(session, MONDAY) == {M}
    assert habits.checked(session, MONDAY + timedelta(days=1)) == {P}


def test_an_old_or_future_day_cannot_change(session: Session) -> None:
    assert habits.toggle(session, MONDAY, M, MONDAY + timedelta(days=3)) is None
    assert habits.toggle(session, MONDAY + timedelta(days=1), M, MONDAY) is None
    assert session.scalar(select(func.count()).select_from(HabitCheck)) == 0


def test_the_week_tally_reads_only_that_week(session: Session) -> None:
    sunday = MONDAY + timedelta(days=6)
    for n in (-1, 0, 2, 6, 7):  # the Sunday before and the Monday after don't count
        on = MONDAY + timedelta(days=n)
        habits.toggle(session, on, M, on)
    assert habits.week(session, MONDAY, sunday)[0] == HabitWeek(M, 3, 7)


def test_a_check_off_belongs_to_the_bound_user(session: Session) -> None:
    habits.toggle(session, MONDAY, M, MONDAY)
    row = session.scalars(select(HabitCheck)).one()
    assert row.user_id == session.info["user_id"]
