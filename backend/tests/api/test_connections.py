"""Connected AI apps on the Account page (ADR-0047 C, mcp-threat-model.md requirement 19)."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests import oauth_flow as flow
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    with flow.app_client(engine) as test_client:
        yield test_client


def _ping(client: TestClient, token: str) -> int:
    body = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    with flow.no_cookies(client):
        return client.post(
            "/mcp", json=body, headers={"authorization": f"Bearer {token}"}
        ).status_code


def test_a_connection_is_listed_with_what_it_may_read(client: TestClient, engine: Engine) -> None:
    flow.connect(client, engine, ["training:read", "body:read"])
    (listed,) = client.get("/api/account/connections").json()
    assert listed["client_name"] == "Claude"
    assert listed["redirect_host"] == "claude.ai"
    assert listed["scopes"] == ["training:read", "body:read"]
    created = datetime.fromisoformat(listed["created_at"])
    assert datetime.fromisoformat(listed["ends_at"]) - created == timedelta(days=90)


def test_revoking_ends_access_and_refresh_at_once_and_alerts(
    client: TestClient, engine: Engine
) -> None:
    app, tokens = flow.connect(client, engine)
    sent = flow.alerts(client)
    assert _ping(client, tokens["access_token"]) == 200
    (listed,) = client.get("/api/account/connections").json()
    assert client.delete(f"/api/account/connections/{listed['id']}").status_code == 204
    assert _ping(client, tokens["access_token"]) == 401
    with flow.no_cookies(client):
        assert flow.refresh(client, app, tokens["refresh_token"]).status_code == 400
    assert client.get("/api/account/connections").json() == []
    assert client.delete(f"/api/account/connections/{listed['id']}").status_code == 404
    assert sent == [
        "An AI app's connection to Training Coach was revoked. It can't read anything now."
    ]


def test_an_ended_connection_is_no_longer_listed(client: TestClient, engine: Engine) -> None:
    flow.mint(engine, ["training:read"])
    with time_machine.travel(datetime.now(UTC) + timedelta(days=90, minutes=1)):
        flow.sign_in_with_link(client, engine)
        assert client.get("/api/account/connections").json() == []


def test_someone_elses_connection_cannot_be_revoked(client: TestClient, engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
    flow.mint(engine, ["training:read"], user=2)
    flow.sign_in_with_link(client, engine)
    assert client.get("/api/account/connections").json() == []
    assert client.delete("/api/account/connections/1").status_code == 404


def test_signed_out_sees_nothing(client: TestClient) -> None:
    assert client.get("/api/account/connections").status_code == 401
    assert client.delete("/api/account/connections/1").status_code == 401
