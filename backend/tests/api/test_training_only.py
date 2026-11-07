"""Members are training-only (ADR-0059, Decided 14): until a lawyer has reviewed the notice, the
consent step and a DPIA, no member can keep or read health data. That covers body measurements
and photos, readiness answers, daily checks, heart rate and band data. It holds with the switch
on, over the web, their AI app and their phone. The owner is untouched."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests import oauth_flow as flow
from tests.api.test_mcp import rpc
from tests.routes import api_routes
from training_coach.api.app import create_app
from training_coach.api.auth import health
from training_coach.config import Settings
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, ingest_keys, users
from training_coach.services.seed import apply_seed, load_plan

MEMBER = 2


@pytest.fixture
def two(engine: Engine) -> Engine:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
        shared.add(User(id=MEMBER, role=users.MEMBER))
        shared.flush()
        apply_seed(shared, load_plan())
    return engine


def _signed_in(engine: Engine, user: int) -> TestClient:
    settings = Settings(
        environment="test", database_url=str(engine.url), public_url=flow.ORIGIN, multi_user=True
    )
    client = TestClient(create_app(settings), base_url=flow.ORIGIN, client=("172.17.0.1", 50000))
    client.__enter__()
    with make_session_factory(engine, user_id=user)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
    return client


@pytest.fixture
def member(two: Engine) -> Iterator[TestClient]:
    client = _signed_in(two, MEMBER)
    yield client
    client.__exit__(None, None, None)


def _gated(client: TestClient) -> list[tuple[str, str]]:
    found = []
    for path, route in api_routes(client.app):  # type: ignore[arg-type]  # a FastAPI app
        if health in {d.call for d in route.dependant.dependencies} and "{" not in path:
            found += [(method, path) for method in sorted(route.methods or ())]
    return found


def test_every_health_route_refuses_a_member(member: TestClient) -> None:
    gated = _gated(member)
    paths = {path for _, path in gated}
    for expected in ("/api/body", "/api/readiness", "/api/daily-check", "/api/account/ingest"):
        assert expected in paths, expected  # the gate is on the routes it should be
    for method, path in gated:
        assert member.request(method, path, json={}).status_code == 403, (method, path)


def test_the_owner_still_reads_their_health(two: Engine) -> None:
    owner = _signed_in(two, users.OWNER)
    try:
        assert owner.get("/api/body").status_code == 200
        assert owner.get("/api/readiness").status_code == 200
    finally:
        owner.__exit__(None, None, None)


def test_a_member_logs_cardio_but_not_its_heart_rate(member: TestClient) -> None:
    walk = {"token": "ab" * 16, "kind": "zone2", "value": 30}
    assert member.post("/api/cardio", json={**walk, "avg_hr": 120}).status_code == 403
    assert member.post("/api/cardio", json=walk).status_code != 403


def test_a_members_ai_app_gets_no_health_scope(member: TestClient, two: Engine) -> None:
    token = flow.mint(two, flow.ALL, user=MEMBER)
    listed = rpc(member, token, "tools/list").json()["result"]["tools"]
    names = {tool["name"] for tool in listed}
    assert "get_summary" in names
    assert not {"get_body", "get_readiness"} & names
    body = {"kind": "body", "measurements": {"bodyweight": 82.4}}
    proposed = rpc(member, token, "tools/call", {"name": "propose_log", "arguments": body})
    assert "aren't available to this person yet" in proposed.text
    # Any heart rate given, even a 0, is refused the same way as by /api/cardio (review of #608).
    walk = {"kind": "cardio", "cardio": "zone2", "minutes": 30, "avg_hr": 0}
    proposed = rpc(member, token, "tools/call", {"name": "propose_log", "arguments": walk})
    assert "aren't available to this person yet" in proposed.text


def test_a_members_phone_is_refused_band_data_with_the_switch_on(
    member: TestClient, two: Engine
) -> None:
    with session_scope(make_session_factory(two, user_id=MEMBER)) as bound:
        secret = ingest_keys.make(bound, datetime.now(UTC))
    headers = {"Authorization": f"Bearer {secret}"}
    assert member.post("/api/ingest/health-connect", json={}, headers=headers).status_code == 403
