from datetime import date, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from training_coach.db.models import Measurement
from training_coach.db.session import make_session_factory
from training_coach.domain.measurements import Kind
from training_coach.services import measurements
from training_coach.services.measurements import Entry
from training_coach.services.users import OWNER

TODAY = date(2026, 10, 10)


def test_a_day_is_saved_and_the_same_kind_replaced(session: Session) -> None:
    assert measurements.save(session, TODAY, TODAY, {Kind.BODYWEIGHT: 83.4, Kind.WAIST: 85}) is None
    assert measurements.save(session, TODAY, TODAY, {Kind.BODYWEIGHT: 83.1}) is None
    earlier = TODAY - timedelta(days=7)
    assert measurements.save(session, earlier, TODAY, {Kind.BODYWEIGHT: 84.0}) is None
    assert measurements.history(session) == [
        Entry(TODAY, Kind.BODYWEIGHT, 83.1),
        Entry(TODAY, Kind.WAIST, 85.0),
        Entry(earlier, Kind.BODYWEIGHT, 84.0),
    ]


def test_nothing_is_saved_when_one_value_is_wrong(session: Session) -> None:
    problem = measurements.save(session, TODAY, TODAY, {Kind.BODYWEIGHT: 83, Kind.WAIST: 820})
    assert problem == "Waist must be from 40 to 200 cm"
    assert measurements.history(session) == []


def test_dates_and_empty_saves_are_refused(session: Session) -> None:
    weight = {Kind.BODYWEIGHT: 83.0}
    tomorrow = TODAY + timedelta(days=1)
    assert measurements.save(session, tomorrow, TODAY, weight) == "that day hasn't happened yet"
    old = TODAY - timedelta(days=15)
    assert measurements.save(session, old, TODAY, weight) == (
        "measurements more than 14 days ago can't be added"
    )
    assert measurements.save(session, TODAY, TODAY, {}) == "nothing to save"


def test_one_measurement_can_be_deleted(session: Session) -> None:
    measurements.save(session, TODAY, TODAY, {Kind.BODYWEIGHT: 83.4, Kind.WAIST: 85})
    assert measurements.delete(session, TODAY, Kind.WAIST)
    assert not measurements.delete(session, TODAY, Kind.WAIST)
    assert [e.kind for e in measurements.history(session)] == [Kind.BODYWEIGHT]


def test_a_save_racing_another_for_the_same_day_and_kind_keeps_one_row(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both saves miss the lookup; the second loses on the unique day and kind and updates."""
    sessions = make_session_factory(engine, user_id=OWNER)
    with sessions() as first:
        measurements.save(first, TODAY, TODAY, {Kind.WAIST: 85})
        first.commit()
    real = measurements._row
    calls: list[int] = []

    def late(*args: object) -> Measurement | None:
        calls.append(1)  # the second save's first lookup ran before the first committed
        return None if len(calls) == 1 else real(*args)  # type: ignore[arg-type]  # passthrough

    monkeypatch.setattr(measurements, "_row", late)
    with sessions() as second:
        measurements._put(second, TODAY, Kind.WAIST, 840)
        second.commit()
    with sessions() as check:
        assert measurements.history(check) == [Entry(TODAY, Kind.WAIST, 84.0)]
    assert len(calls) == 2  # missed, lost the insert, then found and updated the row
