"""The readiness questions (ADR-0046). Pure logic, no I/O.

A short screen before hard exercise, in our own words, on the topics such screens cover. It's
answered once and again every 6 months. Any "yes" means: check with a doctor before hard
efforts. It advises; it never blocks a session.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

VERSION = 1  # bump when the questions change: everyone is asked again
RENEW = timedelta(days=182)  # asked again after about 6 months: health changes


@dataclass(frozen=True)
class Question:
    key: str
    text: str


QUESTIONS: tuple[Question, ...] = (
    Question(
        "heart",
        "Has a doctor ever told you that you have a heart condition or high blood pressure?",
    ),
    Question(
        "chest_pain",
        "Do you get pain, pressure or tightness in your chest, at rest or when you're active?",
    ),
    Question(
        "dizziness",
        "In the last year, have you fainted, or lost your balance because you felt dizzy?",
    ),
    Question(
        "medication",
        "Do you take medicine for your heart, your blood pressure or another long-term condition?",
    ),
    Question(
        "condition",
        "Do you have another condition that could make hard exercise unsafe, such as diabetes, "
        "asthma, or lung or kidney disease?",
    ),
    Question(
        "joints",
        "Do you have a bone, joint or muscle problem that hard exercise could make worse?",
    ),
    Question("pregnancy", "Are you pregnant, or have you given birth in the last 6 months?"),
)
KEYS = frozenset(q.key for q in QUESTIONS)

# The hardest work: all-out intervals, and test days (max efforts, the 12-minute run).
HARD_SESSIONS = frozenset({"hiit"})


class Status(StrEnum):
    DUE = "due"  # never answered, too long ago, or the questions changed
    CLEAR = "clear"
    SEE_DOCTOR = "see_doctor"


def status(
    answers: Mapping[str, bool] | None,
    version: int | None,
    answered: datetime | None,
    now: datetime,
) -> Status:
    if answers is None or answered is None or version != VERSION or now - answered > RENEW:
        return Status.DUE
    return Status.SEE_DOCTOR if any(answers.values()) else Status.CLEAR


DUE_NOTE = (
    "Before hard efforts, answer the readiness questions: seven yes-or-no questions on the "
    "Readiness page."
)
DOCTOR_NOTE = (
    "Your readiness answers say to check with a doctor before hard efforts like this one. "
    "Until you have, keep it easy: stop well short of your limit."
)


def note(current: Status, hard: bool) -> str | None:
    """What Today says, if anything: a nudge to answer when hard work is planned, or the
    doctor advice on a hard day."""
    if not hard or current is Status.CLEAR:
        return None
    return DOCTOR_NOTE if current is Status.SEE_DOCTOR else DUE_NOTE
