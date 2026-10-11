"""A person's heart-rate zones from settings, nights and workouts (ADR-0054)."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from training_coach.db.models import HealthDay, ImportedWorkout
from training_coach.services import zones

TODAY = date(2026, 10, 11)


def test_with_nothing_known_zones_use_the_defaults(session: Session) -> None:
    found = zones.current(session, TODAY)
    assert (found.birth_year, found.own_max, found.estimated_max, found.peak) == (None,) * 4
    assert (found.zones.rest, found.zones.max) == (60, 190)


def test_nights_birth_year_peak_and_own_max(session: Session) -> None:
    for n, bpm in enumerate([50, 52, 48, 70, 51, 49, 50, 90]):
        session.add(HealthDay(local_date=TODAY - timedelta(days=n), resting_hr=bpm))
    session.add(HealthDay(local_date=TODAY + timedelta(days=1), resting_hr=30))  # not yet
    session.add(HealthDay(local_date=TODAY - timedelta(days=20), steps=100))  # no rest
    start = datetime(2026, 10, 10, 15, 0, tzinfo=UTC)
    session.add(
        ImportedWorkout(
            source="com.mi.health",
            start_at=start,
            end_at=start + timedelta(minutes=30),
            local_date=TODAY,
            exercise_type=56,
            minutes=30,
            max_hr=186,
        )
    )
    zones.save(session, 1986, None)
    found = zones.current(session, TODAY)
    assert (found.birth_year, found.estimated_max, found.peak) == (1986, 180, 186)
    assert (found.zones.rest, found.zones.max) == (50, 186)  # the run went above the estimate
    zones.save(session, 1986, 175)
    assert zones.current(session, TODAY).zones.max == 175


def test_what_can_be_saved() -> None:
    assert zones.problem(None, None) is None
    assert zones.problem(1986, 185) is None
    assert zones.problem(1900, None) == "birth year must be from 1920 to 2020"
    assert zones.problem(None, 250) == "max heart rate must be from 120 to 230"
