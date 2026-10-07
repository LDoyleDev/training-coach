"""Habit check-offs (D5, #90): what's ticked for a day, ticking or unticking one, and the
week's tally for the review. Callers pass a session bound to the user (ADR-0029)."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import HabitCheck
from training_coach.domain.habits import WEEK_DAYS, Habit, HabitWeek, can_change, tally


def checked(session: Session, day: date) -> frozenset[Habit]:
    """The habits ticked for ``day``."""
    rows = session.scalars(select(HabitCheck.habit).where(HabitCheck.local_date == day))
    return frozenset(Habit(habit) for habit in rows)


def toggle(session: Session, day: date, habit: Habit, today: date) -> bool | None:
    """Tick ``habit`` for ``day``, or untick it if it was ticked. The new state, or None when
    ``day`` is too long ago (or in the future) to change."""
    if not can_change(day, today):
        return None
    row = session.scalar(
        select(HabitCheck).where(HabitCheck.local_date == day, HabitCheck.habit == habit)
    )
    if row is not None:
        session.delete(row)
        session.flush()
        return False
    session.add(HabitCheck(local_date=day, habit=habit))
    session.flush()
    return True


def week(session: Session, start: date, on: date) -> list[HabitWeek]:
    """Each habit's days done in the week from Monday ``start``, up to ``on``."""
    end = start + timedelta(days=WEEK_DAYS - 1)
    rows = session.execute(
        select(HabitCheck.local_date, HabitCheck.habit).where(
            HabitCheck.local_date >= start, HabitCheck.local_date <= end
        )
    )
    return tally(((day, Habit(habit)) for day, habit in rows), start, on)
