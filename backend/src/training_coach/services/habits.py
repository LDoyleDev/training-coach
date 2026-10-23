"""Habit check-offs (D5, #90): what's ticked for a day, ticking or unticking one, and the
week's tally for the review. Callers pass a session bound to the user (ADR-0029)."""

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import HabitCheck
from training_coach.domain.habits import (
    WEEK_DAYS,
    Habit,
    HabitWeek,
    can_backfill,
    can_change,
    tally,
)


def checked(session: Session, day: date) -> frozenset[Habit]:
    """The habits ticked for ``day``."""
    rows = session.scalars(select(HabitCheck.habit).where(HabitCheck.local_date == day))
    return frozenset(Habit(habit) for habit in rows)


def toggle(session: Session, day: date, habit: Habit, today: date) -> bool | None:
    """Tick ``habit`` for ``day``, or untick it if it was ticked. The new state, or None when
    ``day`` is too long ago (or in the future) to change."""
    if not can_change(day, today):
        return None
    return _flip(session, day, habit)


def _flip(session: Session, day: date, habit: Habit) -> bool:
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


def mark(session: Session, day: date, habit: Habit, done: bool, today: date) -> bool | None:
    """Set ``habit`` for ``day`` to ``done`` (the web's tap, safe to repeat). The new state, or
    None when ``day`` can no longer change."""
    if not can_change(day, today):
        return None
    if (habit in checked(session, day)) == done:
        return done
    return toggle(session, day, habit, today)


def backfill(
    session: Session, day: date, habit: Habit, done: bool, today: date, first: date
) -> bool | None:
    """Set ``habit`` for ``day`` to ``done`` from the web's day view (ADR-0068): any day from
    ``first`` (the account's first day) to today, safe to repeat. None outside that."""
    if not can_backfill(day, today, first):
        return None
    if (habit in checked(session, day)) == done:
        return done
    return _flip(session, day, habit)


def week(session: Session, start: date, on: date) -> list[HabitWeek]:
    """Each habit's days done in the week from Monday ``start``, up to ``on``."""
    end = start + timedelta(days=WEEK_DAYS - 1)
    rows = session.execute(
        select(HabitCheck.local_date, HabitCheck.habit).where(
            HabitCheck.local_date >= start, HabitCheck.local_date <= end
        )
    )
    return tally(((day, Habit(habit)) for day, habit in rows), start, on)
