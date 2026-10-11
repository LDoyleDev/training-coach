"""/api/cardio (ux-flow-plan A1-A3): cardio logged in one step, planned or extra."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Event, SessionTemplate, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, users
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
TOKEN = "0123456789abcdef0123456789abcdef"  # noqa: S105 - a log token, not a secret


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


def _plan_next(engine: Engine, slug: str) -> int:
    """Point the queue at the session ``slug``."""
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        template = bound.scalars(select(SessionTemplate).where(SessionTemplate.slug == slug)).one()
        plan = users.plan_state(bound)
        assert plan is not None
        plan.next_template_id = template.id
        return template.id


def _workouts(engine: Engine) -> list[tuple[int | None, str | None, int]]:
    """Each workout as (template, activity, the first set's value)."""
    with make_session_factory(engine, user_id=OWNER)() as bound:
        return [
            (w.template_id, w.activity, w.sets[0].value) for w in bound.scalars(select(Workout))
        ]


def test_a_planned_zone2_day_offers_done_as_planned(signed_in: TestClient, engine: Engine) -> None:
    _plan_next(engine, "zone2")
    body = signed_in.get("/api/cardio").json()
    assert body["planned"] == {"kind": "zone2", "session": "Long zone 2", "target": 45}
    assert "walk" in body["activities"]
    assert body["week"] == {"zone2": 0, "moderate": 0, "zone2_target": [180, 200]}


def test_a_strength_day_has_nothing_planned_for_cardio(signed_in: TestClient) -> None:
    assert signed_in.get("/api/cardio").json()["planned"] is None


def test_logging_the_planned_cardio_completes_it(signed_in: TestClient, engine: Engine) -> None:
    template = _plan_next(engine, "zone2")
    log = {"token": TOKEN, "kind": "zone2", "value": 62, "activity": "hike"}
    body = signed_in.post("/api/cardio", json=log).json()
    assert body["planned"] is True
    assert body["already_saved"] is False
    assert body["next_session"] not in (None, "Long zone 2")
    assert body["week"]["zone2"] == 62
    assert _workouts(engine) == [(template, "hike", 62)]


def test_cardio_on_a_strength_day_is_an_extra(signed_in: TestClient, engine: Engine) -> None:
    """A walk on a Legs day never completes Legs or moves the queue."""
    log = {"token": TOKEN, "kind": "zone2", "value": 30, "activity": "walk"}
    body = signed_in.post("/api/cardio", json=log).json()
    assert body["planned"] is False
    assert body["next_session"] == "Legs"
    assert _workouts(engine) == [(None, "walk", 30)]
    assert signed_in.get("/api/session/today").json()["session"]["name"] == "Legs"


def test_hiit_logs_rounds(signed_in: TestClient, engine: Engine) -> None:
    template = _plan_next(engine, "hiit")
    planned = signed_in.get("/api/cardio").json()["planned"]
    assert (planned["kind"], planned["target"]) == ("hiit", 8)
    body = signed_in.post("/api/cardio", json={"token": TOKEN, "kind": "hiit", "value": 10})
    assert body.json()["planned"] is True
    assert _workouts(engine) == [(template, None, 10)]


def test_the_same_log_saved_twice_is_saved_once(signed_in: TestClient, engine: Engine) -> None:
    _plan_next(engine, "zone2")
    log = {"token": TOKEN, "kind": "zone2", "value": 45}
    first = signed_in.post("/api/cardio", json=log).json()
    again = signed_in.post("/api/cardio", json=log).json()
    assert again["already_saved"] is True
    assert again["workout_id"] == first["workout_id"]
    assert again["planned"] is False  # nothing completed this time
    assert len(_workouts(engine)) == 1


def test_a_cardio_log_can_be_undone(signed_in: TestClient, engine: Engine) -> None:
    signed_in.post("/api/cardio", json={"token": TOKEN, "kind": "moderate-cardio", "value": 35})
    with make_session_factory(engine, user_id=OWNER)() as bound:
        event = bound.scalars(select(Event).where(Event.kind == "workout.logged")).one()
    assert "undo" in event.payload


@pytest.mark.parametrize(
    "log",
    [
        {"token": TOKEN, "kind": "zone2", "value": 0},
        {"token": TOKEN, "kind": "zone2", "value": 601},
        {"token": TOKEN, "kind": "hiit", "value": 101},
        {"token": TOKEN, "kind": "pull-up", "value": 10},
        {"token": TOKEN, "kind": "zone2", "value": 30, "activity": "teleport"},
        {"token": "not-hex", "kind": "zone2", "value": 30},
    ],
)
def test_bad_logs_are_refused(
    signed_in: TestClient, engine: Engine, log: dict[str, object]
) -> None:
    assert signed_in.post("/api/cardio", json=log).status_code == 422
    assert _workouts(engine) == []


def test_cardio_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/cardio").status_code == 401
        log = {"token": TOKEN, "kind": "zone2", "value": 30}
        assert stranger.post("/api/cardio", json=log).status_code == 401
