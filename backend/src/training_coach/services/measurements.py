"""Body measurements (2-B, #142): saving a day's values and reading them back, the body
settings, and what is worked out from them on read (the 7-day average, the tape estimate,
ADR-0074), never stored. Values are personal: never log them (threat model)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from training_coach.db.models import Measurement, UserSettings
from training_coach.domain import measurements as rules
from training_coach.domain.dates import MAX_DAYS_BACK
from training_coach.domain.measurements import BodyFatEstimate, Kind, from_tenths, to_tenths
from training_coach.services import users


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


def fill(session: Session, on: date, today: date, kind: Kind, value: float) -> bool:
    """Save ``value`` for ``on`` only when that day has none of ``kind`` yet: a reading from the
    scale (ADR-0055) never replaces a typed one or an earlier reading. True if it was saved."""
    tenths = to_tenths(kind, value)
    if isinstance(tenths, str) or _date_problem(on, today) is not None:
        return False
    if _row(session, on, kind) is not None:
        return False
    _put(session, on, kind, tenths)
    return True


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


def on_day(session: Session, on: date) -> dict[Kind, float]:
    """The values saved for ``on``, by kind."""
    rows = session.scalars(select(Measurement).where(Measurement.local_date == on))
    return {Kind(r.kind): from_tenths(r.tenths) for r in rows}


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


def _last_before(session: Session, on: date, kind: Kind) -> tuple[date, float] | None:
    row = session.scalar(
        select(Measurement)
        .where(Measurement.kind == kind.value, Measurement.local_date < on)
        .order_by(Measurement.local_date.desc())
        .limit(1)
    )
    return None if row is None else (row.local_date, from_tenths(row.tenths))


def remeasure(session: Session, on: date, values: Mapping[Kind, float]) -> list[str]:
    """A "re-measure?" warning for each value far from the last earlier entry of its kind
    (ADR-0074), in the kinds' order. Never refuses anything."""
    found = []
    for kind in Kind:
        if kind in values:
            warning = rules.remeasure(kind, on, values[kind], _last_before(session, on, kind))
            if warning is not None:
                found.append(warning)
    return found


@dataclass(frozen=True)
class BodySettings:
    height_cm: int | None
    thigh_offset_cm: int
    body_fat_estimate: BodyFatEstimate


def body_settings(session: Session) -> BodySettings:
    found = users.settings_row(session)
    if found is None:
        return BodySettings(None, rules.DEFAULT_THIGH_OFFSET_CM, BodyFatEstimate.OFF)
    return BodySettings(
        found.height_cm, found.thigh_offset_cm, BodyFatEstimate(found.body_fat_estimate)
    )


def save_settings(session: Session, chosen: BodySettings) -> None:
    """Store the body settings. The caller checks ``rules.settings_problem`` first."""
    found = users.settings_row(session)
    if found is None:
        found = UserSettings()
        session.add(found)
    found.height_cm = chosen.height_cm
    found.thigh_offset_cm = chosen.thigh_offset_cm
    found.body_fat_estimate = chosen.body_fat_estimate.value
    session.flush()


@dataclass(frozen=True)
class Point:
    on: date
    value: float


def estimates(session: Session, since: date | None = None) -> list[Point]:
    """The tape body-fat estimate for each day with both a waist and a neck, newest first;
    none unless the person turned it on and set their height (ADR-0074)."""
    chosen = body_settings(session)
    if chosen.body_fat_estimate is BodyFatEstimate.OFF or chosen.height_cm is None:
        return []
    days: dict[date, dict[Kind, float]] = {}
    for e in history(session):
        if e.kind in (Kind.WAIST, Kind.NECK) and (since is None or e.on >= since):
            days.setdefault(e.on, {})[e.kind] = e.value
    found = []
    for on, both in days.items():  # newest first, as history is
        value = rules.navy_body_fat(chosen.height_cm, both.get(Kind.NECK), both.get(Kind.WAIST))
        if value is not None:
            found.append(Point(on, value))
    return found


@dataclass(frozen=True)
class Average:
    on: date
    value: float  # the mean of the entries in the 7 days ending ``on``
    count: int  # how many entries that is


def averages(session: Session, kind: Kind = Kind.BODYWEIGHT) -> list[Average]:
    """The 7-day average at each day with an entry of ``kind``, newest first."""
    entries = [(e.on, e.value) for e in history(session) if e.kind is kind]
    return [Average(on, value, count) for on, value, count in rules.averages(entries)]
