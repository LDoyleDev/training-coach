"""Baseline tests and retests (2-A, #94, ADR-0037): the bundled plan's tests, saving a test day
and reading them back. Results are checked by ``domain.fitness_tests`` before anything is saved."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from training_coach.db.models import FitnessTestDay
from training_coach.domain.dates import MAX_DAYS_BACK
from training_coach.domain.enums import Side
from training_coach.domain.fitness_tests import FitnessTest, Result, TimeOfDay, problem
from training_coach.services.seed import bundled_plan


@lru_cache(maxsize=1)
def tests() -> tuple[FitnessTest, ...]:
    """Every test in the bundled plan, day 1 first, in plan order."""
    return tuple(sorted((t.test() for t in bundled_plan().tests), key=lambda t: t.day))


@dataclass(frozen=True)
class Conditions:
    """The same short questions each time, so retests are comparable (D4)."""

    time_of_day: TimeOfDay
    fed: bool
    slept_well: bool


@dataclass(frozen=True)
class Saved:
    id: int
    already_saved: bool


@dataclass(frozen=True)
class Day:
    id: int
    on: date
    day: int
    conditions: Conditions
    results: tuple[Result, ...]


def save(
    session: Session,
    on: date,
    today: date,
    day: int,
    conditions: Conditions,
    results: Sequence[Result],
    token: str,
) -> Saved | str:
    """Save one test day, or say why not. The same ``token`` again returns the saved day."""
    existing = _saved(session, token)
    if existing is not None:
        return existing
    if on > today:
        return "that day hasn't happened yet"
    if (today - on).days > MAX_DAYS_BACK:
        return f"tests more than {MAX_DAYS_BACK} days ago can't be added"
    reason = problem(tests(), day, results)
    if reason is not None:
        return reason
    row = FitnessTestDay(
        local_date=on,
        day=day,
        time_of_day=conditions.time_of_day.value,
        fed=conditions.fed,
        slept_well=conditions.slept_well,
        results=[{"test": r.test, "side": r.side.value, "value": r.value} for r in results],
        token=token,
    )
    try:  # a Save racing this one with the same token wins on the unique token
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError:
        return _saved(session, token) or "that test day couldn't be saved; try again"
    return Saved(row.id, already_saved=False)


def _saved(session: Session, token: str) -> Saved | None:
    existing = session.scalar(select(FitnessTestDay).where(FitnessTestDay.token == token))
    return None if existing is None else Saved(existing.id, already_saved=True)


def history(session: Session) -> list[Day]:
    """Every test day, newest first."""
    rows = session.scalars(
        select(FitnessTestDay).order_by(FitnessTestDay.local_date.desc(), FitnessTestDay.id.desc())
    )
    return [
        Day(
            id=row.id,
            on=row.local_date,
            day=row.day,
            conditions=Conditions(TimeOfDay(row.time_of_day), row.fed, row.slept_well),
            results=tuple(Result(r["test"], Side(r["side"]), r["value"]) for r in row.results),
        )
        for row in rows
    ]
