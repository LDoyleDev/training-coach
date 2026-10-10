"""/api/account/ai: the person's own Groq key (ADR-0047 B). Checked, encrypted, never sent back."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
import time_machine
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, select

from tests.api.test_erase import ORIGIN, TELEGRAM
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import AiConnection, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

KEY = "gsk_" + "a" * 48 + "4f2a"
MODELS = "https://api.groq.com/openai/v1/models"
NOTHING = {
    "available": True,
    "connected": False,
    "ends_in": None,
    "enabled": False,
    "body": False,
    "readiness": False,
    "failed": False,
}


def _client(engine: Engine, secrets_key: str | None) -> Iterator[TestClient]:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
        shared.get_one(User, OWNER).telegram_user_id = TELEGRAM
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(
        environment="test",
        database_url=str(engine.url),
        public_url=ORIGIN,
        secrets_key=SecretStr(secrets_key) if secrets_key else None,
    )
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    yield from _client(engine, Fernet.generate_key().decode())


@pytest.fixture
def alerts(signed_in: TestClient) -> list[str]:
    sent: list[str] = []

    async def notify(text: str) -> None:
        sent.append(text)

    signed_in.app.state.notify = notify  # type: ignore[attr-defined]  # a FastAPI app
    return sent


def test_nothing_stored_at_first(signed_in: TestClient) -> None:
    assert signed_in.get("/api/account/ai").json() == NOTHING


@respx.mock
def test_a_key_is_checked_then_kept_encrypted(
    signed_in: TestClient, engine: Engine, alerts: list[str]
) -> None:
    groq = respx.get(MODELS).respond(json={"data": []})
    response = signed_in.put("/api/account/ai/key", json={"key": KEY})
    assert response.status_code == 200
    assert response.json() == NOTHING | {"connected": True, "ends_in": "4f2a", "enabled": True}
    assert KEY not in response.text
    assert groq.calls.last.request.headers["Authorization"] == f"Bearer {KEY}"
    assert alerts == ["An AI key was added to Training Coach."]
    with session_scope(make_session_factory(engine, user_id=OWNER)) as session:
        stored = session.scalars(select(AiConnection.groq_key)).one()
    assert KEY.encode() not in stored
    assert KEY not in signed_in.get("/api/account/ai").text


@respx.mock
@pytest.mark.parametrize(("groq", "code"), [(httpx.Response(401), 400), (httpx.Response(503), 503)])
def test_a_key_groq_refuses_is_not_kept(
    signed_in: TestClient, groq: httpx.Response, code: int
) -> None:
    respx.get(MODELS).mock(return_value=groq)
    assert signed_in.put("/api/account/ai/key", json={"key": KEY}).status_code == code
    assert signed_in.get("/api/account/ai").json() == NOTHING


@respx.mock
@pytest.mark.parametrize(
    "key", ["sk-ant-123456789012345678901234", "gsk_short", "gsk_" + "a" * 30 + "\n"]
)
def test_something_that_is_not_a_groq_key_never_leaves(signed_in: TestClient, key: str) -> None:
    groq = respx.get(MODELS).respond(json={"data": []})
    assert signed_in.put("/api/account/ai/key", json={"key": key}).status_code == 422
    assert not groq.called


@respx.mock
def test_options_test_and_remove(signed_in: TestClient) -> None:
    respx.get(MODELS).respond(json={"data": []})
    signed_in.put("/api/account/ai/key", json={"key": KEY})
    choice = {"enabled": False, "body": True, "readiness": True}
    assert signed_in.put("/api/account/ai", json=choice).json() == NOTHING | {
        "connected": True,
        "ends_in": "4f2a",
        **choice,
    }
    assert signed_in.post("/api/account/ai/test").status_code == 204
    assert signed_in.delete("/api/account/ai/key").status_code == 204
    assert signed_in.get("/api/account/ai").json() == NOTHING
    assert signed_in.delete("/api/account/ai/key").status_code == 404
    assert signed_in.put("/api/account/ai", json=choice).status_code == 404
    assert signed_in.post("/api/account/ai/test").status_code == 404


@respx.mock
def test_storing_a_key_needs_a_recent_sign_in(signed_in: TestClient, alerts: list[str]) -> None:
    groq = respx.get(MODELS).respond(json={"data": []})
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        assert signed_in.put("/api/account/ai/key", json={"key": KEY}).status_code == 403
    assert not groq.called
    assert alerts == []
    assert signed_in.get("/api/account/ai").json() == NOTHING


@respx.mock
def test_the_test_button_records_what_groq_said(signed_in: TestClient) -> None:
    groq = respx.get(MODELS)
    groq.respond(json={"data": []})
    signed_in.put("/api/account/ai/key", json={"key": KEY})
    groq.respond(401)
    assert signed_in.post("/api/account/ai/test").status_code == 400
    assert signed_in.get("/api/account/ai").json()["failed"]
    groq.respond(503)  # can't tell: the status stays as it was
    assert signed_in.post("/api/account/ai/test").status_code == 503
    assert signed_in.get("/api/account/ai").json()["failed"]
    groq.respond(json={"data": []})
    assert signed_in.post("/api/account/ai/test").status_code == 204
    assert not signed_in.get("/api/account/ai").json()["failed"]


@pytest.fixture
def no_secrets(engine: Engine) -> Iterator[TestClient]:
    yield from _client(engine, None)


@respx.mock
def test_without_a_secrets_key_nothing_can_be_stored(no_secrets: TestClient) -> None:
    groq = respx.get(MODELS).respond(json={"data": []})
    assert no_secrets.get("/api/account/ai").json() == NOTHING | {"available": False}
    assert no_secrets.put("/api/account/ai/key", json={"key": KEY}).status_code == 409
    assert no_secrets.post("/api/account/ai/test").status_code == 409
    assert not groq.called


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/account/ai"),
        ("PUT", "/api/account/ai/key"),
        ("DELETE", "/api/account/ai/key"),
        ("PUT", "/api/account/ai"),
        ("POST", "/api/account/ai/test"),
    ],
)
def test_signed_out_gets_nothing(client: TestClient, method: str, path: str) -> None:
    assert client.request(method, path, json={}).status_code == 401
