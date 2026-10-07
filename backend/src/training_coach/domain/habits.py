"""Habit check-offs (phase 2 step 2-D, D5 in docs/specs/phase-2-decisions.md). Pure logic.

Three habits are ticked once a day. The weekly review shows how many days each was done out
of the days so far ("5 of 7"); there are no streaks to break.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

WEEK_DAYS = 7
# A check-off can be changed for today and the two days before: Wind-down is often ticked the
# next morning, and an evening message is still answerable after a missed day.
LATE_DAYS = 2


class Habit(StrEnum):
    MORNING_LIGHT = "morning_light"
    PROTEIN = "protein"
    WIND_DOWN = "wind_down"


LABELS = {
    Habit.MORNING_LIGHT: "Morning light",
    Habit.PROTEIN: "Protein target",
    Habit.WIND_DOWN: "Wind-down",
}
HINTS = {
    Habit.MORNING_LIGHT: "outside within an hour of waking: about 10 minutes when clear, "
    "20-30 when cloudy",
    Habit.PROTEIN: "your daily protein goal reached",
    Habit.WIND_DOWN: "no screens or bright light in the last hour before bed",
}


@dataclass(frozen=True)
class HabitWeek:
    habit: Habit
    done: int  # days ticked
    days: int  # days of the week so far, up to 7


def can_change(day: date, today: date) -> bool:
    """Whether a check-off for ``day`` may still be changed on ``today``."""
    return 0 <= (today - day).days <= LATE_DAYS


def tally(checked: Iterable[tuple[date, Habit]], start: date, on: date) -> list[HabitWeek]:
    """Each habit's days done in the week from Monday ``start``, counting days up to ``on``."""
    days = max(0, min(WEEK_DAYS, (on - start).days + 1))
    window = {start + timedelta(days=n) for n in range(days)}
    seen = {(day, habit) for day, habit in checked if day in window}
    return [HabitWeek(h, sum(1 for _, done in seen if done is h), days) for h in Habit]
