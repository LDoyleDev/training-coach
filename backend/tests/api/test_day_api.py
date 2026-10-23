"""/api/day (ADR-0068): a day's log for Today, owner-only, today or earlier only."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, update

from tests import factories
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import SetLog, User, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.queue import local_date
from training_coach.services import auth
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


def _today() -> date:
    return local_date(datetime.now(UTC), Settings().tz)


def _logged(engine: Engine, on: date) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        pull = factories.exercise(mine)
        plan = factories.template(mine, pull)
        workout = Workout(local_date=on, status=WorkoutStatus.DONE, template_id=plan.id)
        workout.sets = [
            SetLog(
                exercise_id=pull.id,
                ladder_step_id=pull.ladder[0].id,
                set_no=1,
                side=Side.BOTH,
                value=6,
            )
        ]
        mine.add(workout)


def test_today_lists_what_was_logged(signed_in: TestClient, engine: Engine) -> None:
    _logged(engine, _today())
    view = signed_in.get("/api/day").json()
    assert view["day"] == view["today"] == _today().isoformat()
    (workout,) = view["workouts"]
    assert (workout["name"], workout["status"], workout["planned"]) == ("Upper", "done", True)
    assert workout["exercises"] == [
        {
            "name": "Pull-up",
            "unit": "reps",
            "step": "Negatives",
            "sets": [{"set_no": 1, "left": 6, "right": None}],
        }
    ]


def test_an_earlier_day_and_its_bounds(signed_in: TestClient, engine: Engine) -> None:
    earlier = _today() - timedelta(days=3)
    _logged(engine, earlier)
    view = signed_in.get(f"/api/day?on={earlier.isoformat()}").json()
    assert view["day"] == view["first"] == earlier.isoformat()  # the first workout is the start
    assert len(view["workouts"]) == 1
    yesterday = signed_in.get(f"/api/day?on={(_today() - timedelta(days=1)).isoformat()}")
    assert yesterday.json()["workouts"] == []


def test_a_later_day_or_one_before_the_first_is_refused(
    signed_in: TestClient, engine: Engine
) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        mine.execute(update(User).values(created_at=datetime.now(UTC)))
    tomorrow = (_today() + timedelta(days=1)).isoformat()
    assert signed_in.get(f"/api/day?on={tomorrow}").status_code == 422
    long_ago = (_today() - timedelta(days=30)).isoformat()
    assert signed_in.get(f"/api/day?on={long_ago}").status_code == 422
    assert signed_in.get("/api/day?on=not-a-day").status_code == 422


def test_signed_out_gets_nothing(client: TestClient) -> None:
    assert client.get("/api/day").status_code == 401
