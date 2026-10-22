"""Storing Health Connect Webhook payloads (ADR-0055)."""

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
from training_coach.services import health_import, measurements, zones

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
    assert (walk.avg_hr, walk.max_hr) == (round((8 * 100 + 38 * 140) / 46), 143)

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
    assert walk.max_hr == 143


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


def test_a_night_sent_again_longer_updates_the_same_row(session: Session) -> None:
    """Health Connect sends only the end and the length; a night still open at one sync and
    longer at the next has another derived start, and must not count twice."""
    early_end = hcw.SLEEP_END - timedelta(hours=1)
    first = {
        **hcw.sleep(),
        "session_end_time": hcw.iso(early_end),
        "duration_seconds": int((early_end - hcw.SLEEP_START).total_seconds()) - 600,
    }
    _store(session, {"sleep": [first]})
    _store(session, {"sleep": [hcw.sleep()]})
    (night,) = session.scalars(select(SleepSession))
    assert (night.start_at, night.end_at) == (hcw.SLEEP_START, hcw.SLEEP_END)
    assert night.asleep_min == 440


def test_a_later_higher_resting_record_keeps_the_days_low(session: Session) -> None:
    _store(session, {"resting_heart_rate": [{"bpm": 48, "time": "2026-10-11T06:00:00Z"}]})
    _store(session, {"resting_heart_rate": [{"bpm": 55, "time": "2026-10-11T07:00:00Z"}]})
    day = _day(session, TODAY)
    assert day is not None
    assert (day.resting_hr, day.resting_source) == (48, "record")


def _zone_minutes(walk: ImportedWorkout) -> list[int | None]:
    return [walk.zone1_min, walk.zone2_min, walk.zone3_min, walk.zone4_min, walk.zone5_min]


def test_a_workout_gets_its_zone_minutes(session: Session) -> None:
    _store(session, hcw.full())
    (walk,) = session.scalars(select(ImportedWorkout))
    # Resting 48 from the night, max 190 without an age: 140 bpm is zone 2, 100 below zone 1.
    assert _zone_minutes(walk) == [0, 38, 0, 0, 0]


def test_changing_max_heart_rate_counts_zones_again(session: Session) -> None:
    _store(session, hcw.full())
    zones.save(session, None, 150)
    health_import.rezone(session, TODAY, hcw.NOW)
    (walk,) = session.scalars(select(ImportedWorkout))
    assert _zone_minutes(walk) == [8, 0, 0, 0, 38]
    # Once its heart rate has aged out, a workout keeps the minutes it had.
    zones.save(session, None, None)
    health_import.rezone(session, TODAY, hcw.NOW + timedelta(days=9))
    assert _zone_minutes(walk) == [8, 0, 0, 0, 38]


def test_a_workout_without_heart_rate_has_no_zones(session: Session) -> None:
    _store(session, {"exercise": [hcw.walk()]})
    (walk,) = session.scalars(select(ImportedWorkout))
    assert _zone_minutes(walk) == [None] * 5


# ---------------------------------------------------- v1.9.23 on: ids, edits and deletions


def test_a_night_is_kept_by_its_id_when_edited(session: Session) -> None:
    """An edit comes again with the same id: a night moved so it no longer overlaps the one
    stored still replaces it."""
    _store(session, {"sleep": [hcw.identified(hcw.sleep(), hcw.NIGHT_ID)]})
    later = hcw.SLEEP_START - timedelta(hours=3)  # an evening nap, it turns out
    moved = {**hcw.sleep(), "session_end_time": hcw.iso(later), "duration_seconds": 3600}
    _store(session, {"sleep": [hcw.identified(moved, hcw.NIGHT_ID)]})
    (night,) = session.scalars(select(SleepSession))
    assert (night.record_id, night.end_at) == (hcw.NIGHT_ID, later)


def test_overlapping_records_with_their_own_ids_stay_apart(session: Session) -> None:
    """A nap inside a night, each its own Health Connect record: two rows, and deleting one
    removes only that one (review of #283)."""
    nap_end = hcw.SLEEP_START + timedelta(hours=2)
    nap = {**hcw.sleep(), "session_end_time": hcw.iso(nap_end), "duration_seconds": 1800}
    _store(session, {"sleep": [hcw.identified(hcw.sleep(), hcw.NIGHT_ID)]})
    _store(session, {"sleep": [hcw.identified(nap, "nap-id")]})
    found = {row.record_id: row.end_at for row in session.scalars(select(SleepSession))}
    assert found == {hcw.NIGHT_ID: hcw.SLEEP_END, "nap-id": nap_end}
    _store(session, hcw.changes(deleted=[{"type": "sleep", "id": "nap-id"}]))
    assert [row.record_id for row in session.scalars(select(SleepSession))] == [hcw.NIGHT_ID]


def test_a_night_stored_without_an_id_takes_its_id_when_sent_again(session: Session) -> None:
    _store(session, {"sleep": [hcw.sleep()]})
    _store(session, {"sleep": [hcw.identified(hcw.sleep(), hcw.NIGHT_ID)]})
    (night,) = session.scalars(select(SleepSession))
    assert night.record_id == hcw.NIGHT_ID


def test_another_record_at_the_same_start_replaces_the_row(session: Session) -> None:
    # Source and start are unique: a second record there can't be a second row.
    _store(session, {"sleep": [hcw.identified(hcw.sleep(), hcw.NIGHT_ID)]})
    _store(session, {"sleep": [hcw.identified(hcw.sleep(), "rewritten-id")]})
    (night,) = session.scalars(select(SleepSession))
    assert night.record_id == "rewritten-id"


def test_a_deleted_night_is_removed_and_its_rest_derived_again(session: Session) -> None:
    _store(session, hcw.full() | {"sleep": [hcw.identified(hcw.sleep(), hcw.NIGHT_ID)]})
    assert _day(session, TODAY).resting_hr == 48  # type: ignore[union-attr]
    _store(session, hcw.changes(deleted=[{"type": "sleep", "id": hcw.NIGHT_ID}]))
    assert list(session.scalars(select(SleepSession))) == []
    # Without the night, rest comes from midnight to six Berlin time (22:00-04:00 UTC).
    assert _day(session, TODAY).resting_hr == 48  # type: ignore[union-attr]


def test_a_deleted_workout_is_removed_unless_counted(session: Session) -> None:
    gone = hcw.changes(deleted=[{"type": "exercise", "id": hcw.WALK_ID}])
    for status in ("new", "dismissed"):
        _store(session, {"exercise": [hcw.identified(hcw.walk(), hcw.WALK_ID)]})
        session.scalars(select(ImportedWorkout)).one().status = status
        session.commit()
        _store(session, gone)
        assert list(session.scalars(select(ImportedWorkout))) == []

    _store(session, {"exercise": [hcw.identified(hcw.walk(), hcw.WALK_ID)]})
    (walk,) = session.scalars(select(ImportedWorkout))
    walk.status = "counted"
    session.commit()
    _store(session, gone)
    assert [w.status for w in session.scalars(select(ImportedWorkout))] == ["counted"]


def test_a_workout_whose_start_was_edited_stays_one_row(session: Session) -> None:
    _store(session, {"exercise": [hcw.identified(hcw.walk(), hcw.WALK_ID)]})
    (walk,) = session.scalars(select(ImportedWorkout))
    walk.status = "dismissed"
    session.commit()
    start = hcw.WALK_START - timedelta(minutes=5)
    edited = {**hcw.walk(), "start_time": hcw.iso(start)}
    _store(session, {"exercise": [hcw.identified(edited, hcw.WALK_ID)]})
    (walk,) = session.scalars(select(ImportedWorkout))
    assert (walk.start_at, walk.minutes, walk.status) == (start, 51, "dismissed")


def test_an_edited_start_meeting_an_older_row_keeps_the_one_acted_on(session: Session) -> None:
    # Stored before ids were sent, at the new start; then the id-carrying one, counted.
    start = hcw.WALK_START - timedelta(minutes=5)
    _store(session, {"exercise": [{**hcw.walk(), "start_time": hcw.iso(start)}]})
    _store(session, {"exercise": [hcw.identified(hcw.walk(), hcw.WALK_ID)]})
    counted = session.scalars(select(ImportedWorkout).where(ImportedWorkout.record_id.is_not(None)))
    counted.one().status = "counted"
    session.commit()
    edited = {**hcw.walk(), "start_time": hcw.iso(start)}
    _store(session, {"exercise": [hcw.identified(edited, hcw.WALK_ID)]})
    (walk,) = session.scalars(select(ImportedWorkout))
    assert (walk.start_at, walk.status, walk.record_id) == (start, "counted", hcw.WALK_ID)


def test_deletions_of_other_types_are_ignored_and_bad_ones_skipped() -> None:
    body = hcw.changes(
        deleted=[
            {"type": "heart_rate", "id": "x1"},
            {"type": "steps", "id": "x2"},
            {"type": "sleep"},
            {"type": "exercise", "id": hcw.WALK_ID},
        ]
    )
    batch = health_import.parse(body, hcw.NOW)
    assert batch.deleted == {"exercise": {hcw.WALK_ID}}
    assert dict(batch.skipped) == {"deleted": 1}
    assert not batch.taken
    assert dict(health_import.parse({"deleted": {}}, hcw.NOW).skipped) == {"deleted": 1}


def test_local_time_with_an_offset_is_the_same_instant(session: Session) -> None:
    """v1.9.25 writes Berlin time with its offset by default; stored as the same instants."""
    night = {
        **hcw.sleep(),
        "session_end_time": hcw.local(hcw.SLEEP_END),
        "stages": [],
    }
    walk = {
        **hcw.walk(),
        "start_time": hcw.local(hcw.WALK_START),
        "end_time": hcw.local(hcw.WALK_END),
    }
    _store(session, hcw.changes(sleep=[night], exercise=[walk]))
    assert session.scalars(select(SleepSession.end_at)).one() == hcw.SLEEP_END
    assert session.scalars(select(ImportedWorkout.start_at)).one() == hcw.WALK_START


def test_many_deletions_are_applied_in_chunks(session: Session) -> None:
    _store(session, {"sleep": [hcw.identified(hcw.sleep(), hcw.NIGHT_ID)]})
    deleted = [{"type": "sleep", "id": f"other-{n}"} for n in range(1200)]
    deleted.append({"type": "sleep", "id": hcw.NIGHT_ID})
    _store(session, hcw.changes(deleted=deleted))
    assert list(session.scalars(select(SleepSession))) == []
