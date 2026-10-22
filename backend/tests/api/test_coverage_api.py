from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.session import make_session_factory
from training_coach.services import auth
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as signed_in:
        with make_session_factory(engine, user_id=OWNER)() as bound:
            apply_seed(bound, load_plan())
            token = auth.create_link(bound, datetime.now(UTC))
            bound.commit()
        assert signed_in.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield signed_in


def test_coverage_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as stranger:
        assert stranger.get("/api/plan/coverage").status_code == 401


def test_coverage_gives_each_muscle_its_band_and_warnings(client: TestClient) -> None:
    body = client.get("/api/plan/coverage").json()
    assert (body["main_on_target"], body["main_total"]) == (2, 10)
    assert (body["session_cap"], body["spine_cap"], body["grip_cap"]) == (11, 8, 8)
    assert (body["minimum"], body["ceiling"], body["back_to_back"]) == (4, 30, 4)
    muscles = {m["muscle"]: m for m in body["muscles"]}
    assert len(muscles) == 21
    assert [m["main"] for m in body["muscles"][:10]] == [True] * 10
    glutes = muscles["glutes"]
    assert (glutes["sets"], glutes["days"], glutes["band"]) == (12.5, 1, "light green")
    assert (glutes["one_day"], glutes["over_session_cap"], glutes["most_in"]) == (
        True,
        True,
        "Legs",
    )
    assert {s["exercise"] for s in glutes["sources"]} >= {"Kettlebell swing", "Pistol squat"}
    assert muscles["triceps"]["missing_parts"] == ["triceps long head"]
    assert (muscles["neck"]["low"], muscles["neck"]["high"], muscles["neck"]["evidence"]) == (
        3,
        9,
        "low",
    )
    assert muscles["quads"]["evidence"] is None
    legs = body["sessions"][0]
    assert legs == {
        "session": "Legs",
        "spine_sets": 6,
        "grip_sets": 3,
        "spine_heavy": False,
        "grip_heavy": False,
    }
