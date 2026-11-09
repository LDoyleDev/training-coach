"""Consent per category (ADR-0090). Pure logic, no I/O.

Each category of health data, and the walk-through's answers, opens for a member only once
they've said yes to it, at the wording version shown. The owner is never asked: it's their own
data. The record is append-only, so the latest entry per category is the current answer.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Category(StrEnum):
    BODY = "body"  # measurements (resting heart rate typed in too), photos, body settings
    DAILY_CHECK = "daily_check"
    BAND = "band"  # band import and its data, heart rate on cardio, heart-rate settings
    WALKTHROUGH = "walkthrough"  # the walk-through's answers; never the safety questions


class Answer(StrEnum):
    GIVEN = "given"
    WITHDRAWN = "withdrawn"


# The wording version for each category, which the web shows. Bump one when its wording
# changes: everyone who gave it is asked again. The walk-through's 2: minutes, kit and places
# became settings, not answers (ADR-0090 addendum, 9 Nov 2026).
VERSIONS: dict[Category, int] = {**dict.fromkeys(Category, 1), Category.WALKTHROUGH: 2}


@dataclass(frozen=True)
class Entry:
    category: Category
    answer: Answer
    version: int
    at: datetime


def latest(entries: list[Entry]) -> dict[Category, Entry]:
    """The last entry per category, in the order they were written. Not by ``at``: a clock that
    steps back (an NTP correction, the Pi's clock reset) mustn't let an earlier yes outrank a
    withdrawal (review of #617). ``at`` is for showing when."""
    return {entry.category: entry for entry in entries}


def is_open(entry: Entry | None) -> bool:
    """Whether a member's category is open: given, to the wording shown now."""
    return (
        entry is not None
        and entry.answer is Answer.GIVEN
        and entry.version == VERSIONS[entry.category]
    )
