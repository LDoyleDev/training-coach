"""Habit check-offs (phase 2 step 2-D, D5 in docs/specs/phase-2-decisions.md). Pure logic.

Three habits are ticked once a day. The weekly review shows how many days each was done out
of the days so far ("5 of 7"); there are no streaks to break.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

WEEK_DAYS = 7
PROTEIN_GRAMS = (40, 400)  # a daily target outside this is a typo
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
# What counts as done (Huberman Lab: light, sleep and nutrition episodes). Shown under the
# buttons in the evening message and in /habits, so a tick means the same thing every day.
HINTS = {
    Habit.MORNING_LIGHT: (
        "outside within an hour of waking, not through a window: about 5-10 minutes on a "
        "clear morning, 15-20 when cloudy, up to 30 when very overcast. No sunglasses, and "
        "never look straight at the sun. Before sunrise, put bright lights on and go out "
        "once it's up."
    ),
    Habit.PROTEIN: (
        "about 1.6-2.2 g per kg of bodyweight across the day (roughly 130-175 g at 80 kg), "
        "spread over 3-4 meals with 30-50 g each, one of them soon after training. "
        "General guidance for healthy adults: with kidney disease, or if pregnant, ask a doctor."
    ),
    Habit.WIND_DOWN: (
        "the last hour before bed with no phone, laptop or TV, and only dim, low lights. "
        "Keep the room cool and dark, and go to bed at about the same time each night."
    ),
}


def label(habit: Habit, protein_g: int | None = None) -> str:
    """The button text: the protein target names its number once it's set."""
    if habit is Habit.PROTEIN and protein_g is not None:
        return f"{LABELS[habit]} ({protein_g} g)"
    return LABELS[habit]


def hint(habit: Habit, protein_g: int | None = None) -> str:
    """What counts as done; the protein one uses the person's own number once it's set."""
    if habit is Habit.PROTEIN and protein_g is not None:
        return (
            f"{protein_g} g across the day, spread over 3-4 meals with 30-50 g each, one of "
            "them soon after training. General guidance for healthy adults: with kidney "
            "disease, or if pregnant, ask a doctor."
        )
    return HINTS[habit]


def protein_grams(text: str) -> int | None:
    """A daily protein target typed as a whole number of grams ("165"), or None."""
    words = text.strip().lower().removesuffix("g").strip()
    if not (words.isascii() and words.isdecimal()):
        return None
    grams = int(words)
    return grams if PROTEIN_GRAMS[0] <= grams <= PROTEIN_GRAMS[1] else None


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
