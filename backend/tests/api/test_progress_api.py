"""/api/progress: each exercise's standing for the web app, owner-only."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth
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


def test_every_planned_exercise_is_listed_with_its_step(signed_in: TestClient) -> None:
    standings = signed_in.get("/api/progress").json()
    assert standings[0]["exercise"] == "Jump squat"  # the first in the Legs session
    first = standings[0]
    assert (first["step_number"], first["last"], first["best_set"], first["recent"]) == (
        1,
        [],
        None,
        [],
    )
    assert first["status"] == "hold"
    assert {s["unit"] for s in standings} >= {"reps", "seconds", "minutes"}
    assert not any(s["retired"] for s in standings)  # retired ones only show with history


def test_progress_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/progress").status_code == 401
