"""/api/band/offers: band workouts counted as cardio after one tap (ADR-0054)."""

from datetime import UTC, date, datetime, time, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from tests.api.test_cardio import _plan_next, _undo, _workouts
from tests.api.test_cardio import signed_in as signed_in  # a shared fixture
from tests.api.test_erase import ORIGIN
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import ImportedWorkout, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import band_cardio
from training_coach.services.users import OWNER

PATH = "/api/band/offers"
BERLIN = Settings(environment="test").tz


def _today() -> date:
    return local_date(datetime.now(UTC), BERLIN)


def _band(
    engine: Engine,
    *,
    days_ago: int = 0,
    activity: str | None = "walk",
    minutes: int = 46,
    zones: tuple[int, ...] | None = (8, 38, 0, 0, 0),
) -> int:
    """A workout as the band import stores it."""
    on = _today() - timedelta(days=days_ago)
    start = datetime.combine(on, time(7, 0), tzinfo=BERLIN).astimezone(UTC)
    row = ImportedWorkout(
        source="com.mi.health",
        start_at=start,
        end_at=start + timedelta(minutes=minutes),
        local_date=on,
        exercise_type=79,
        activity=activity,
        minutes=minutes,
    )
    if zones is not None:
        row.zone1_min, row.zone2_min, row.zone3_min, row.zone4_min, row.zone5_min = zones
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        mine.add(row)
        mine.flush()
        return row.id


def test_a_band_walk_is_offered(signed_in: TestClient, engine: Engine) -> None:
    walk = _band(engine)
    _band(engine, days_ago=1, activity=None)  # not cardio
    _band(engine, days_ago=2, minutes=8, zones=None)  # too short
    _band(engine, days_ago=7, zones=None)  # too old
    (offer,) = signed_in.get(PATH).json()
    assert offer == {
        "id": walk,
        "on": _today().isoformat(),
        "activity": "walk",
        "minutes": 46,
        "zone2": 38,
        "kind": "zone2",
        "value": 38,
        "text": "Walk, 46 min, 38 in zone 2 - count it?",
    }


def test_counting_on_a_zone2_day_completes_it_once(signed_in: TestClient, engine: Engine) -> None:
    template = _plan_next(engine, "zone2")
    walk = _band(engine)
    body = signed_in.post(f"{PATH}/{walk}/count").json()
    assert (body["planned"], body["already_saved"]) == (True, False)
    assert body["week"]["zone2"] == 38  # the zone 2 minutes feed the week
    assert _workouts(engine) == [(template, "walk", 38)]
    again = signed_in.post(f"{PATH}/{walk}/count").json()
    assert (again["already_saved"], again["workout_id"]) == (True, body["workout_id"])
    assert len(_workouts(engine)) == 1
    assert signed_in.get(PATH).json() == []


def test_counting_on_a_strength_day_is_an_extra(signed_in: TestClient, engine: Engine) -> None:
    body = signed_in.post(f"{PATH}/{_band(engine)}/count").json()
    assert body["planned"] is False
    assert _workouts(engine) == [(None, "walk", 38)]


def test_an_earlier_day_is_an_extra_on_that_day(signed_in: TestClient, engine: Engine) -> None:
    _plan_next(engine, "zone2")
    walk = _band(engine, days_ago=2)
    assert signed_in.post(f"{PATH}/{walk}/count").json()["planned"] is False
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        (workout,) = mine.scalars(select(Workout))
        assert (workout.template_id, workout.local_date) == (None, _today() - timedelta(days=2))


def test_undo_takes_it_back_and_it_is_offered_again(signed_in: TestClient, engine: Engine) -> None:
    walk = _band(engine)
    signed_in.post(f"{PATH}/{walk}/count")
    _undo(engine)
    assert _workouts(engine) == []
    assert [o["id"] for o in signed_in.get(PATH).json()] == [walk]
    assert signed_in.post(f"{PATH}/{walk}/count").json()["already_saved"] is False
    assert len(_workouts(engine)) == 1


def test_not_this_one(signed_in: TestClient, engine: Engine) -> None:
    walk = _band(engine)
    assert signed_in.post(f"{PATH}/{walk}/dismiss").status_code == 204
    assert signed_in.get(PATH).json() == []
    assert signed_in.post(f"{PATH}/{walk}/count").status_code == 404
    assert signed_in.post(f"{PATH}/999/dismiss").status_code == 404
    assert signed_in.post(f"{PATH}/999/count").status_code == 404
    assert _workouts(engine) == []


def test_a_workout_too_short_to_count_isnt_counted(signed_in: TestClient, engine: Engine) -> None:
    easy = _band(engine, zones=(40, 2, 0, 0, 0))
    assert signed_in.get(PATH).json() == []
    assert signed_in.post(f"{PATH}/{easy}/count").status_code == 404


def test_dismissing_marks_it(engine: Engine) -> None:
    walk = _band(engine)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        row = mine.get_one(ImportedWorkout, walk)
        row.workout_id = None
        assert band_cardio.dismiss(mine, walk) is True
        assert row.status == "dismissed"


def test_strangers_get_nothing(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get(PATH).status_code == 401
        assert stranger.post(f"{PATH}/1/count").status_code == 401
        assert stranger.post(f"{PATH}/1/dismiss").status_code == 401
