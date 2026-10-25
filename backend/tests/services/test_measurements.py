from datetime import date, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from training_coach.db.models import Measurement
from training_coach.db.session import make_session_factory
from training_coach.domain.measurements import BodyFatEstimate, Kind
from training_coach.services import measurements
from training_coach.services.measurements import Average, Entry, Point
from training_coach.services.users import OWNER

TODAY = date(2026, 10, 10)
NAVY = BodyFatEstimate.NAVY_MALE


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


# ------------------------------------------------- the protocol and the estimate (ADR-0076)


def test_a_far_value_is_warned_about_against_the_last_earlier_day(session: Session) -> None:
    old, last = date(2026, 9, 1), date(2026, 10, 3)
    measurements.save(session, old, old, {Kind.WAIST: 80.0})
    measurements.save(session, last, TODAY, {Kind.WAIST: 85.0, Kind.NECK: 39.0})
    measurements.save(session, TODAY, TODAY, {Kind.WAIST: 95.0})  # the same day: not compared
    values = {Kind.NECK: 41.0, Kind.WAIST: 88.5, Kind.CHEST: 100.0}
    assert measurements.remeasure(session, TODAY, values) == [
        "Waist is 3.5 cm off your last (3 Oct): different landmark? Re-measure.",
        "Neck is 2.0 cm off your last (3 Oct): different landmark? Re-measure.",
    ]
    assert measurements.remeasure(session, last, {Kind.WAIST: 85.0}) == [
        "Waist is 5.0 cm off your last (1 Sep): different landmark? Re-measure."
    ]


def test_body_settings_start_at_their_defaults_and_are_saved(session: Session) -> None:
    assert measurements.body_settings(session) == measurements.BodySettings(
        None, 15, BodyFatEstimate.OFF
    )
    chosen = measurements.BodySettings(182, 12, BodyFatEstimate.NAVY_MALE)
    measurements.save_settings(session, chosen)
    assert measurements.body_settings(session) == chosen


def test_the_estimate_needs_the_setting_the_height_and_both_tapes(session: Session) -> None:
    both, waist_only = date(2026, 10, 3), date(2026, 10, 5)
    measurements.save(session, both, TODAY, {Kind.WAIST: 93.0, Kind.NECK: 39.0})
    measurements.save(session, waist_only, TODAY, {Kind.WAIST: 94.0})
    measurements.save(session, TODAY, TODAY, {Kind.WAIST: 94.0, Kind.NECK: 39.0})
    assert measurements.estimates(session) == []  # off
    measurements.save_settings(session, measurements.BodySettings(None, 15, NAVY))
    assert measurements.estimates(session) == []  # no height
    measurements.save_settings(session, measurements.BodySettings(182, 15, NAVY))
    assert measurements.estimates(session) == [Point(TODAY, 21.6), Point(both, 20.9)]
    assert measurements.estimates(session, since=date(2026, 10, 4)) == [Point(TODAY, 21.6)]
    assert {e.kind for e in measurements.history(session)} == {Kind.WAIST, Kind.NECK}  # not stored


def test_the_bodyweight_average_is_worked_out_on_read(session: Session) -> None:
    measurements.save(session, date(2026, 10, 1), TODAY, {Kind.BODYWEIGHT: 84.0})
    measurements.save(session, date(2026, 10, 7), TODAY, {Kind.BODYWEIGHT: 83.0, Kind.WAIST: 90})
    measurements.save(session, date(2026, 10, 8), TODAY, {Kind.BODYWEIGHT: 82.6})
    assert measurements.averages(session) == [
        Average(date(2026, 10, 8), 82.8, 2),
        Average(date(2026, 10, 7), 83.5, 2),
        Average(date(2026, 10, 1), 84.0, 1),
    ]
