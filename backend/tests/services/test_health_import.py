"""Storing Health Connect Webhook payloads (ADR-0054)."""

from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from tests import hcw_payloads as hcw
from training_coach.db.models import (
    HealthDay,
    HeartRateSample,
    ImportedWorkout,
    Measurement,
    SleepSession,
)
from training_coach.domain.measurements import Kind
from training_coach.services import health_import, measurements

BERLIN = ZoneInfo("Europe/Berlin")
TODAY = date(2026, 10, 11)


def _store(session: Session, body: dict[str, Any], now: datetime = hcw.NOW) -> None:
    health_import.store(session, health_import.parse(body, now), BERLIN, now)
    session.commit()


def _day(session: Session, day: date) -> HealthDay | None:
    return session.scalar(select(HealthDay).where(HealthDay.local_date == day))


def test_a_full_sync_lands_in_every_table(session: Session) -> None:
    batch = health_import.parse(hcw.full(), hcw.NOW)
    assert dict(batch.taken) == {
        "steps": 3,
        "sleep": 1,
        "heart_rate": 46 + 450,
        "exercise": 1,
        "weight": 2,
    }
    assert not batch.skipped
    _store(session, hcw.full())

    (night,) = session.scalars(select(SleepSession))
    assert (night.source, night.local_date) == ("com.mi.health", TODAY)
    assert (night.start_at, night.end_at) == (hcw.SLEEP_START, hcw.SLEEP_END)
    assert (night.asleep_min, night.awake_min) == (440, 10)
    assert (night.light_min, night.deep_min, night.rem_min) == (250, 90, 100)

    assert _day(session, date(2026, 10, 9)).steps == 6500  # type: ignore[union-attr]
    assert _day(session, date(2026, 10, 10)).steps == 11234  # type: ignore[union-attr]
    today = _day(session, TODAY)
    assert today is not None
    assert (today.steps, today.resting_hr, today.resting_source) == (812, 48, "derived")

    (walk,) = session.scalars(select(ImportedWorkout))
    assert (walk.activity, walk.exercise_type, walk.minutes, walk.status) == ("walk", 79, 46, "new")
    assert walk.local_date == date(2026, 10, 10)
    assert (walk.avg_hr, walk.max_hr) == (round((8 * 100 + 38 * 125) / 46), 128)

    assert measurements.history(session)[0].value == 81.5  # the first reading of the day
    assert session.scalar(select(HeartRateSample.id).limit(1)) is not None


def test_sending_the_same_payload_again_changes_nothing(session: Session) -> None:
    _store(session, hcw.full())
    _store(session, hcw.full())
    assert len(list(session.scalars(select(SleepSession)))) == 1
    assert len(list(session.scalars(select(ImportedWorkout)))) == 1
    assert len(list(session.scalars(select(HeartRateSample)))) == 46 + 450
    assert len(list(session.scalars(select(Measurement)))) == 1
    assert _day(session, TODAY).steps == 812  # type: ignore[union-attr]


def test_a_day_keeps_its_larger_step_count(session: Session) -> None:
    def steps(count: int, start: str) -> dict[str, Any]:
        return {"steps": [{"count": count, "start_time": start, "end_time": hcw.iso(hcw.NOW)}]}

    _store(session, steps(812, "2026-10-10T22:00:00Z"))
    _store(session, steps(1500, "2026-10-10T22:00:00Z"))  # the day grew
    _store(session, steps(300, "2026-10-11T06:00:00Z"))  # a partial day at the window's edge
    assert _day(session, TODAY).steps == 1500  # type: ignore[union-attr]


def test_heart_rate_arriving_after_its_workout_fills_it_in(session: Session) -> None:
    _store(session, {"exercise": [hcw.walk()]})
    (walk,) = session.scalars(select(ImportedWorkout))
    assert walk.avg_hr is None
    _store(session, {"heart_rate": hcw.walk_heart_rate()})
    session.refresh(walk)
    assert walk.max_hr == 128


def test_a_resting_heart_rate_record_wins_over_the_derived_one(session: Session) -> None:
    _store(session, {"resting_heart_rate": [{"bpm": 52, "time": "2026-10-11T06:00:00Z"}]})
    _store(session, hcw.full())
    day = _day(session, TODAY)
    assert day is not None
    assert (day.resting_hr, day.resting_source) == (52, "record")


def test_without_sleep_rest_comes_from_midnight_to_six(session: Session) -> None:
    _store(session, {"heart_rate": hcw.night_heart_rate()})
    assert _day(session, TODAY).resting_hr == 48  # type: ignore[union-attr]


def test_heart_rate_older_than_eight_days_is_deleted(session: Session) -> None:
    _store(session, {"heart_rate": hcw.walk_heart_rate()})
    later = hcw.NOW + timedelta(days=9)
    _store(session, {"heart_rate": [hcw.bucket(later - timedelta(minutes=5), 70)]}, now=later)
    assert len(list(session.scalars(select(HeartRateSample)))) == 1


def test_a_scale_reading_never_replaces_a_typed_weight(session: Session) -> None:
    assert measurements.save(session, TODAY, TODAY, {Kind.BODYWEIGHT: 80.0}) is None
    _store(session, hcw.full())
    assert measurements.history(session)[0].value == 80.0


def test_records_that_dont_fit_are_skipped_and_counted() -> None:
    body = {
        "steps": [{"count": -1, "start_time": "2026-10-11T00:00:00Z", "end_time": "x"}],
        "heart_rate": [
            hcw.bucket(hcw.NOW, 300),  # impossible
            {"bpm": 60, "time": "2026-10-11T06:00:00"},  # no time zone
            hcw.bucket(hcw.NOW - timedelta(days=40), 60),  # long ago
            hcw.bucket(hcw.NOW, 61),
        ],
        "exercise": [{**hcw.walk(), "end_time": "2026-10-09T00:00:00Z"}],  # ends before start
        "weight": "81",
        "sleep": [{**hcw.sleep(), "stages": [{"stage": "deep"}]}],
        "nutrition": [{"calories": 900}],  # a type we don't use
    }
    batch = health_import.parse(body, hcw.NOW)
    assert dict(batch.taken) == {"heart_rate": 1}
    assert dict(batch.skipped) == {
        "steps": 1,
        "heart_rate": 3,
        "exercise": 1,
        "weight": 1,
        "sleep": 1,
    }
    assert health_import.counts(batch) == {
        "heart_rate": 1,
        "steps_skipped": 1,
        "heart_rate_skipped": 3,
        "exercise_skipped": 1,
        "weight_skipped": 1,
        "sleep_skipped": 1,
    }


def test_full_resolution_samples_are_averaged_per_minute() -> None:
    body = {
        "heart_rate": [
            {"bpm": 60, "time": "2026-10-11T07:00:05Z"},
            {"bpm": 70, "time": "2026-10-11T07:00:45Z"},
        ]
    }
    (minute,) = health_import.parse(body, hcw.NOW).heart_rate
    assert (minute.bpm, minute.low, minute.high) == (65, 60, 70)
