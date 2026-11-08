"""A member's health data only with their consent (ADR-0090): each category (body, daily check,
band) is closed to a member until they say yes to it, over the web, their AI app and their
phone, even with the switch on; a yes opens that category and no other. The owner is never
asked."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests import oauth_flow as flow
from tests.api.test_mcp import rpc
from tests.routes import api_routes
from training_coach.api.app import create_app
from training_coach.api.auth import HEALTH_GATES
from training_coach.config import Settings
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.consent import Category
from training_coach.services import auth, consent, ingest_keys, users
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
        if HEALTH_GATES & {d.call for d in route.dependant.dependencies} and "{" not in path:
            found += [(method, path) for method in sorted(route.methods or ())]
    return found


def _consent(engine: Engine, *categories: Category) -> None:
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as bound:
        for category in categories:
            consent.give(bound, category, datetime.now(UTC))


def test_every_health_route_refuses_a_member(member: TestClient) -> None:
    gated = _gated(member)
    paths = {path for _, path in gated}
    for expected in ("/api/body", "/api/daily-check", "/api/account/ingest"):
        assert expected in paths, expected  # the gate is on the routes it should be
    # The health questions are answered on the device: members answer them too (ADR-0085).
    assert "/api/readiness" not in paths
    assert member.get("/api/readiness").json()["due"] is True
    for method, path in gated:
        refused = member.request(method, path, json={})
        assert refused.status_code == 403, (method, path)
        assert set(refused.json()["detail"]) == {"consent_needed"}, (method, path)


def test_a_yes_opens_that_category_and_no_other(member: TestClient, two: Engine) -> None:
    _consent(two, Category.BODY)
    assert member.get("/api/body").status_code == 200
    assert member.get("/api/account/body").status_code == 200
    refused = member.get("/api/daily-check")
    assert (refused.status_code, refused.json()["detail"]) == (
        403,
        {"consent_needed": "daily_check"},
    )
    assert member.get("/api/health").json()["detail"] == {"consent_needed": "band"}
    _consent(two, Category.DAILY_CHECK, Category.BAND)
    for path in ("/api/daily-check", "/api/health", "/api/account/heart-rate"):
        assert member.get(path).status_code == 200, path


def test_the_owner_still_reads_their_health(two: Engine) -> None:
    owner = _signed_in(two, users.OWNER)
    try:
        assert owner.get("/api/body").status_code == 200
        assert owner.get("/api/readiness").status_code == 200
    finally:
        owner.__exit__(None, None, None)


def test_a_member_logs_cardio_but_its_heart_rate_only_with_band_consent(
    member: TestClient, two: Engine
) -> None:
    walk = {"token": "ab" * 16, "kind": "zone2", "value": 30}
    assert member.post("/api/cardio", json={**walk, "avg_hr": 120}).status_code == 403
    assert member.post("/api/cardio", json=walk).status_code != 403
    _consent(two, Category.BAND)
    again = {**walk, "token": "cd" * 16, "avg_hr": 120}
    assert member.post("/api/cardio", json=again).status_code != 403


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


def test_a_members_ai_app_gets_each_health_scope_with_its_consent(
    member: TestClient, two: Engine
) -> None:
    _consent(two, Category.BODY)
    token = flow.mint(two, flow.ALL, user=MEMBER)
    names = {tool["name"] for tool in rpc(member, token, "tools/list").json()["result"]["tools"]}
    assert "get_body" in names
    assert "get_readiness" not in names  # the daily check needs its own yes
    _consent(two, Category.DAILY_CHECK)
    names = {tool["name"] for tool in rpc(member, token, "tools/list").json()["result"]["tools"]}
    assert "get_readiness" in names


def test_a_members_phone_is_let_in_with_band_consent(member: TestClient, two: Engine) -> None:
    with session_scope(make_session_factory(two, user_id=MEMBER)) as bound:
        secret = ingest_keys.make(bound, datetime.now(UTC))
    _consent(two, Category.BAND)
    headers = {"Authorization": f"Bearer {secret}"}
    assert member.post("/api/ingest/health-connect", json={}, headers=headers).status_code != 403
