from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.session import make_session_factory
from training_coach.services import auth
from training_coach.services.seed import load_plan
from training_coach.services.users import OWNER


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    """Signed in: the plan is private like every page (ADR-0041)."""
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as signed_in:
        with make_session_factory(engine, user_id=OWNER)() as bound:
            token = auth.create_link(bound, datetime.now(UTC))
            bound.commit()
        assert signed_in.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield signed_in


def test_the_plan_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as stranger:
        assert stranger.get("/api/plan").status_code == 401


def test_plan_endpoint_returns_the_week_in_queue_order(client: TestClient) -> None:
    body = client.get("/api/plan").json()
    plan = load_plan()
    assert [s["slug"] for s in body["sessions"]] == [s.slug for s in plan.sessions]
    assert [s["position"] for s in body["sessions"]] == list(range(len(plan.sessions)))
    assert {s["type"] for s in body["sessions"]} == {"strength", "conditioning", "recovery"}


def test_plan_endpoint_exercise_details(client: TestClient) -> None:
    torso = next(s for s in client.get("/api/plan").json()["sessions"] if s["slug"] == "torso")
    pull_up = next(e for e in torso["exercises"] if e["slug"] == "pull-up")
    assert pull_up["ladder"][pull_up["start_step"]] == "Strict pull-up"
    assert torso["total_sets"] == sum(e["sets"] for e in torso["exercises"])


def test_plan_endpoint_volume_excludes_qualities(client: TestClient) -> None:
    body = client.get("/api/plan").json()
    groups = {v["group"] for v in body["volume"]}
    assert "quads" in groups
    assert not groups & {"conditioning", "mobility", "power", "posture"}
    assert (body["volume_target_min"], body["volume_target_max"]) == (10, 20)


def test_plan_endpoint_has_security_headers(client: TestClient) -> None:
    response = client.get("/api/plan")
    assert response.status_code == 200
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]


def test_plan_endpoint_exposes_only_static_plan_fields(client: TestClient) -> None:
    """ADR-0019: /api/plan was public, so its shape is locked (owner-only since ADR-0041).
    Adding a field (above all any
    per-user progress, log or measurement) must be a deliberate change to this test and the ADR.
    """
    body = client.get("/api/plan").json()
    assert set(body) == {"sessions", "volume", "volume_target_min", "volume_target_max"}
    assert {k for s in body["sessions"] for k in s} == {
        "position",
        "slug",
        "name",
        "focus",
        "type",
        "optional",
        "total_sets",
        "exercises",
    }
    assert {k for s in body["sessions"] for e in s["exercises"] for k in e} == {
        "slug",
        "name",
        "kind",
        "sets",
        "rep_min",
        "rep_max",
        "per_side",
        "muscle_groups",
        "ladder",
        "start_step",
    }
    assert {k for v in body["volume"] for k in v} == {"group", "sets"}
