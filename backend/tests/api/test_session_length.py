"""PUT /api/session/length (ADR-0082): short on time today, and the Today view's length."""

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import SessionProgress
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


def _choose(
    client: TestClient, minutes: int | None, keep: list[str] | None = None, revision: int = 0
) -> Any:
    session = client.get("/api/session/today").json()["session"]
    body = {
        "template_id": session["template_id"],
        "place": session["place"],
        "revision": revision,
        "minutes": minutes,
        "keep": keep or [],
    }
    return client.put("/api/session/length", json=body)


def test_today_offers_the_lengths_and_says_how_long_as_planned(signed_in: TestClient) -> None:
    session = signed_in.get("/api/session/today").json()["session"]
    assert session["length"] == {
        "minutes": None,
        "options": [40, 30, 20],
        "keep": [],
        "planned_minutes": session["minutes"],
        "dropped": [],
        "warm_up": "full",
        "shortest": None,
        "fixed": False,
    }


def test_a_shorter_day_names_what_it_drops_and_a_reload_keeps_it(signed_in: TestClient) -> None:
    answer = _choose(signed_in, 20, ["hamstring-curl"])
    assert answer.status_code == 200
    today = answer.json()
    length = today["session"]["length"]
    assert (length["minutes"], length["keep"], length["warm_up"]) == (
        20,
        ["hamstring-curl"],
        "ramp",
    )
    assert length["dropped"] == [
        "Single-leg calf raise",
        "Tibialis raise",
        "Single-leg Romanian deadlift",  # with the hamstring curl kept, it covers the hamstrings
        "Pistol squat",
    ]
    assert today["session"]["minutes"] <= 20
    assert today["progress"]["revision"] == 2
    names = {i["name"]: i["targets"] for i in today["session"]["items"]}
    assert names["Tibialis raise"] == []  # still listed: every set keeps its index
    assert signed_in.get("/api/session/today").json()["session"]["length"] == length


def test_the_length_is_fixed_once_a_set_is_kept(signed_in: TestClient) -> None:
    today = _choose(signed_in, 30).json()
    kept = {
        "template_id": today["session"]["template_id"],
        "place": today["session"]["place"],
        "revision": today["progress"]["revision"],
        "position": 1,
        "sets": [{"item": 0, "set_no": 1, "left": 6}],
    }
    assert signed_in.put("/api/session/progress", json=kept).status_code == 200
    answer = _choose(signed_in, 20, revision=3)
    assert answer.status_code == 409
    assert answer.json()["detail"] == "this session has started: its length stays as it is"
    length = signed_in.get("/api/session/today").json()["session"]["length"]
    assert (length["minutes"], length["fixed"]) == (30, True)


def test_a_stale_browser_or_another_session_is_a_conflict(signed_in: TestClient) -> None:
    assert _choose(signed_in, 30).status_code == 200
    assert _choose(signed_in, 20, revision=1).status_code == 409
    body = {"template_id": 99999, "place": "home", "minutes": 20}
    assert signed_in.put("/api/session/length", json=body).status_code == 409


def test_odd_minutes_or_a_keep_outside_the_session_are_refused(
    signed_in: TestClient, engine: Engine
) -> None:
    assert _choose(signed_in, 25).status_code == 422
    answer = _choose(signed_in, 20, ["pull-up"])
    assert answer.status_code == 422
    assert answer.json()["detail"] == "that exercise isn't in today's session"
    with make_session_factory(engine, user_id=OWNER)() as bound:
        assert bound.scalars(select(SessionProgress)).all() == []  # nothing written


def test_strangers_are_refused(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        body = {"template_id": 1, "place": "home", "minutes": 20}
        assert client.put("/api/session/length", json=body).status_code == 401
