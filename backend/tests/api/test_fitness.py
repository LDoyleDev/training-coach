"""/api/tests (2-A, #94): baseline tests and retests, owner-only."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.session import make_session_factory
from training_coach.services import auth
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
DAY_1 = {
    "day": 1,
    "time_of_day": "morning",
    "fed": False,
    "slept_well": True,
    "token": "t" * 20,
    "results": [
        {"test": "max-pull-ups", "side": "both", "value": 8},
        {"test": "dead-hang", "side": "both", "value": 52},
    ],
}


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


def test_the_tests_come_with_units_and_ranges(signed_in: TestClient) -> None:
    tests = signed_in.get("/api/tests").json()
    toe = next(t for t in tests if t["slug"] == "toe-touch")
    assert (toe["day"], toe["unit"], toe["low"], toe["high"]) == (2, "cm", -60, 60)
    assert [t["day"] for t in tests] == sorted(t["day"] for t in tests)


def test_a_test_day_is_saved_once_and_listed(signed_in: TestClient) -> None:
    saved = signed_in.post("/api/tests", json=DAY_1)
    assert saved.status_code == 200
    assert saved.json()["already_saved"] is False
    again = signed_in.post("/api/tests", json=DAY_1).json()
    assert again == {"id": saved.json()["id"], "already_saved": True}
    (day,) = signed_in.get("/api/tests/results").json()
    assert (day["day"], day["time_of_day"], day["fed"], day["slept_well"]) == (
        1,
        "morning",
        False,
        True,
    )
    assert day["results"] == DAY_1["results"]


@pytest.mark.parametrize(
    "change",
    [
        {"results": []},
        {"results": [{"test": "toe-touch", "side": "both", "value": 3}]},  # a day 2 test
        {"results": [{"test": "dead-hang", "side": "both", "value": 99999}]},
        {"on": "2099-01-01"},
    ],
)
def test_results_are_checked_before_saving(
    signed_in: TestClient, change: dict[str, object]
) -> None:
    assert signed_in.post("/api/tests", json={**DAY_1, **change}).status_code == 422
    assert signed_in.get("/api/tests/results").json() == []


@pytest.mark.parametrize("change", [{"time_of_day": "night"}, {"token": "short"}])
def test_a_malformed_body_is_refused(signed_in: TestClient, change: dict[str, object]) -> None:
    assert signed_in.post("/api/tests", json={**DAY_1, **change}).status_code == 422


def test_tests_need_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/tests").status_code == 401
        assert stranger.get("/api/tests/results").status_code == 401
        assert stranger.post("/api/tests", json=DAY_1).status_code == 401
