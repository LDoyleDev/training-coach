"""Which test day is due (D4, #95, ADR-0038): the cadence from ``domain.retests``, the test days
saved, and the block start when blocks are on."""

from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import FitnessTestDay
from training_coach.domain import retests
from training_coach.domain.retests import PastTest
from training_coach.services import blocks, fitness_tests


@dataclass(frozen=True)
class TestDayDue:
    day: int  # 1 or 2
    name: str  # "Retest, day 1"
    tests: tuple[str, ...]  # the tests' names, in plan order


def done(session: Session) -> list[PastTest]:
    return [
        PastTest(on, day)
        for on, day in session.execute(select(FitnessTestDay.local_date, FitnessTestDay.day))
    ]


def due(
    session: Session, on: date, tz: ZoneInfo, saved: list[PastTest] | None = None
) -> TestDayDue | None:
    """The test day due on ``on``, or None. ``saved`` stands in for the test days in the
    database (the week ahead adds the ones it plans)."""
    past = done(session) if saved is None else saved
    day = retests.due(on, past, blocks.start(session, on, tz))
    if day is None:
        return None
    names = tuple(t.name for t in fitness_tests.tests() if t.day == day)
    return TestDayDue(day, retests.name(day, past), names) if names else None
