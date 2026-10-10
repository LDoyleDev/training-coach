"""Body measurements (2-B, #142): saving a day's values and reading them back. Values are
personal: never log them (threat model)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from training_coach.db.models import Measurement
from training_coach.domain.dates import MAX_DAYS_BACK
from training_coach.domain.measurements import Kind, from_tenths, to_tenths


@dataclass(frozen=True)
class Entry:
    on: date
    kind: Kind
    value: float


def _date_problem(on: date, today: date) -> str | None:
    if on > today:
        return "that day hasn't happened yet"
    if (today - on).days > MAX_DAYS_BACK:
        return f"measurements more than {MAX_DAYS_BACK} days ago can't be added"
    return None


def save(session: Session, on: date, today: date, values: Mapping[Kind, float]) -> str | None:
    """Save ``values`` for ``on``, replacing any of the same kind that day. Nothing is saved if
    any value is out of range; returns why, or None."""
    if not values:
        return "nothing to save"
    problem = _date_problem(on, today)
    if problem is not None:
        return problem
    stored: dict[Kind, int] = {}
    for kind, value in values.items():
        tenths = to_tenths(kind, value)
        if isinstance(tenths, str):
            return tenths
        stored[kind] = tenths
    for kind, tenths in stored.items():
        _put(session, on, kind, tenths)
    return None


def _row(session: Session, on: date, kind: Kind) -> Measurement | None:
    return session.scalar(
        select(Measurement).where(Measurement.local_date == on, Measurement.kind == kind.value)
    )


def _put(session: Session, on: date, kind: Kind, tenths: int) -> None:
    row = _row(session, on, kind)
    if row is not None:
        row.tenths = tenths
        return
    try:  # another save of the same day and kind at the same moment wins the insert
        with session.begin_nested():
            session.add(Measurement(local_date=on, kind=kind.value, tenths=tenths))
            session.flush()
    except IntegrityError:
        raced = _row(session, on, kind)
        if raced is not None:
            raced.tenths = tenths
    session.flush()


def history(session: Session) -> list[Entry]:
    """Every measurement, newest day first, in the kinds' order within a day."""
    order = list(Kind)
    rows = session.scalars(select(Measurement).order_by(Measurement.local_date.desc()))
    entries = [Entry(r.local_date, Kind(r.kind), from_tenths(r.tenths)) for r in rows]
    return sorted(entries, key=lambda e: (-e.on.toordinal(), order.index(e.kind)))


def delete(session: Session, on: date, kind: Kind) -> bool:
    row = _row(session, on, kind)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True
