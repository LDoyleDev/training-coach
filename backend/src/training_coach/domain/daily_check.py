"""The daily check (ADR-0053): three one-tap questions before training, and the advice they
give. Pure logic, no I/O.

Sleep, soreness and energy, each with a good, a middle and a worst answer. Two worst answers
say rest today; one worst, or two middles, say go lighter; anything else, go as planned. It
advises; it never changes the plan by itself.
"""

from dataclasses import dataclass
from enum import StrEnum


class Sleep(StrEnum):
    GOOD = "good"
    OK = "ok"
    POOR = "poor"


class Soreness(StrEnum):
    NONE = "none"
    SOME = "some"
    A_LOT = "a_lot"


class Energy(StrEnum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Advice(StrEnum):
    AS_PLANNED = "as_planned"
    LIGHTER = "lighter"
    REST = "rest"


@dataclass(frozen=True)
class Answers:
    sleep: Sleep
    soreness: Soreness
    energy: Energy


@dataclass(frozen=True)
class Question:
    key: str  # the field in Answers
    text: str
    options: tuple[tuple[str, str], ...]  # (value, label), best first, worst last


QUESTIONS: tuple[Question, ...] = (
    Question(
        "sleep",
        "How did you sleep?",
        ((Sleep.GOOD, "Good"), (Sleep.OK, "OK"), (Sleep.POOR, "Poorly")),
    ),
    Question(
        "soreness",
        "How sore are you?",
        ((Soreness.NONE, "Not sore"), (Soreness.SOME, "A bit sore"), (Soreness.A_LOT, "Very sore")),
    ),
    Question(
        "energy",
        "How's your energy?",
        ((Energy.HIGH, "High"), (Energy.NORMAL, "Normal"), (Energy.LOW, "Low")),
    ),
)

WORST = frozenset({Sleep.POOR, Soreness.A_LOT, Energy.LOW})
MIDDLE = frozenset({Sleep.OK, Soreness.SOME, Energy.NORMAL})


def advise(answers: Answers) -> Advice:
    """Two worst answers: rest. One worst, or two middles: lighter. Otherwise as planned."""
    given = (answers.sleep, answers.soreness, answers.energy)
    worst = sum(a in WORST for a in given)
    middle = sum(a in MIDDLE for a in given)
    if worst >= 2:
        return Advice.REST
    if worst == 1 or middle >= 2:
        return Advice.LIGHTER
    return Advice.AS_PLANNED


TITLES = {
    Advice.AS_PLANNED: "Go as planned",
    Advice.LIGHTER: "Go lighter today",
    Advice.REST: "Take a rest day",
}
TEXTS = {
    Advice.AS_PLANNED: "You're good to go. Train as planned.",
    Advice.LIGHTER: (
        "Train, but ease off: an easier step or a set fewer, and stop a few reps short of your "
        "limit. Keep cardio easy."
    ),
    Advice.REST: (
        "Your body is asking for a break. Rest today: the session moves to tomorrow. A walk is "
        "fine, unless you have a fever or feel ill: then rest."
    ),
}


def summary(answers: Answers) -> str:
    """One line for Today and the bot: "Slept OK, a bit sore, normal energy: go lighter today"."""
    sleep = {Sleep.GOOD: "Slept well", Sleep.OK: "Slept OK", Sleep.POOR: "Slept poorly"}
    sore = {Soreness.NONE: "not sore", Soreness.SOME: "a bit sore", Soreness.A_LOT: "very sore"}
    said = f"{sleep[answers.sleep]}, {sore[answers.soreness]}, {answers.energy.value} energy"
    return f"{said}: {TITLES[advise(answers)].lower()}"
