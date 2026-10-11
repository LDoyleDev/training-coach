"""/api/home: the home screen for the web app, owner-only."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import SessionTemplate
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, users
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"


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


def test_home_before_anything_is_done(signed_in: TestClient) -> None:
    found = signed_in.get("/api/home").json()
    assert found["totals"] == {
        "sessions": 0,
        "sets": 0,
        "reps": 0,
        "cardio_minutes": 0,
        "first_day": None,
        "days": 0,
    }
    assert (found["week"]["done"], found["week"]["planned"]) == (0, 7)
    assert found["week"]["zone2_target"] == [180, 200]
    assert found["progress"] == {"steps_climbed": 0, "ready": [], "bests": []}
    assert found["recent"] == []
    assert isinstance(found["today"], str)


def test_home_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/home").status_code == 401


def test_recent_cardio_says_what_it_was(signed_in: TestClient, engine: Engine) -> None:
    """A walk on a strength day reads "Walk, 30 min"; the planned zone 2 names the session."""
    log = {"token": "ab" * 16, "kind": "zone2", "value": 30, "activity": "walk"}
    assert signed_in.post("/api/cardio", json=log).status_code == 200
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        template = bound.scalars(select(SessionTemplate).where(SessionTemplate.slug == "zone2"))
        plan = users.plan_state(bound)
        assert plan is not None
        plan.next_template_id = template.one().id
    log = {"token": "cd" * 16, "kind": "zone2", "value": 62, "activity": "hike"}
    assert signed_in.post("/api/cardio", json=log).status_code == 200
    log = {"token": "ef" * 16, "kind": "moderate-cardio", "value": 20}
    assert signed_in.post("/api/cardio", json=log).status_code == 200
    recent = [r["session"] for r in signed_in.get("/api/home").json()["recent"]]
    assert recent == ["Extra", "Long zone 2: hike, 62 min", "Walk, 30 min"]
