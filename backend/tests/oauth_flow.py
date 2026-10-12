"""Connecting an AI app end to end, for tests (ADR-0047 C): register, authorize, prove a
passkey on the consent page, approve, and exchange the code, as Claude.ai and a phone would.

Values are low-entropy fakes (gitleaks scans every branch)."""

import base64
import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine

from tests.passkey_device import Device
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import OAuthClient
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, mcp_tokens
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
RP_ID = "coach.example.com"
MCP = f"{ORIGIN}/mcp"
CALLBACK = "https://claude.ai/api/mcp/auth_callback"
VERIFIER = "ab" * 22
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=")
ADDRESS = "203.0.113.5"  # the AI app's servers (TEST-NET-3)
ALL = ["training:read", "body:read", "readiness:read", "log:propose"]


@contextmanager
def app_client(engine: Engine) -> Iterator[TestClient]:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    # The tunnel reaches the app from the Docker bridge, naming the caller in CF-Connecting-IP.
    with TestClient(create_app(settings), base_url=ORIGIN, client=("172.17.0.1", 50000)) as client:
        yield client


def alerts(client: TestClient) -> list[str]:
    sent: list[str] = []

    async def notify(text: str) -> None:
        sent.append(text)

    client.app.state.notify = notify  # type: ignore[attr-defined]  # a FastAPI app
    return sent


def register(client: TestClient, address: str = ADDRESS, **metadata: Any) -> Response:
    body = {"client_name": "Claude", "redirect_uris": [CALLBACK]} | metadata
    return client.post("/oauth/register", json=body, headers={"cf-connecting-ip": address})


def client_id(client: TestClient, address: str = ADDRESS) -> str:
    answer = register(client, address)
    assert answer.status_code == 201, answer.text
    found: str = answer.json()["client_id"]
    return found


BROWSER = "198.18.0.1"  # the person's phone (a benchmarking range: never a real caller)


def authorize(
    client: TestClient, app: str, browser: str = BROWSER, **changes: str | None
) -> Response:
    params: dict[str, str | None] = {
        "response_type": "code",
        "client_id": app,
        "redirect_uri": CALLBACK,
        "code_challenge": CHALLENGE.decode(),
        "code_challenge_method": "S256",
        "resource": MCP,
        "scope": " ".join(ALL),
        "state": "st-1",
    } | changes
    query = {k: v for k, v in params.items() if v is not None}
    return client.get(
        "/oauth/authorize",
        params=query,
        headers={"cf-connecting-ip": browser},
        follow_redirects=False,
    )


def handle(client: TestClient, app: str, browser: str = BROWSER, **changes: str | None) -> str:
    answer = authorize(client, app, browser, **changes)
    assert answer.status_code == 303, answer.text
    location = answer.headers["location"]
    assert location.startswith("/connect#")
    return location.removeprefix("/connect#")


def query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def sign_in_with_link(client: TestClient, engine: Engine) -> None:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    client.cookies.delete("__Host-tc_session")
    assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204


def _options(client: TestClient, path: str) -> dict[str, Any]:
    answer = client.post(path)
    assert answer.status_code == 200, answer.text
    options: dict[str, Any] = json.loads(answer.text)
    return options


def add_passkey(client: TestClient, engine: Engine) -> Device:
    """A passkey for the owner, added from a fresh link sign-in (before any passkey exists)."""
    sign_in_with_link(client, engine)
    device = Device(ORIGIN, RP_ID)
    options = _options(client, "/api/auth/passkeys/register/options")
    added = client.post(
        "/api/auth/passkeys/register", json={"credential": device.register(options)}
    )
    assert added.status_code == 204
    return device


def sign_in_with_passkey(client: TestClient, device: Device) -> None:
    client.cookies.delete("__Host-tc_session")
    options = _options(client, "/api/auth/passkeys/sign-in/options")
    answer = client.post("/api/auth/passkeys/sign-in", json={"credential": device.sign_in(options)})
    assert answer.status_code == 204


def approve(
    client: TestClient, consent: str, app: str, scopes: list[str] | None = None, **changes: str
) -> Response:
    assert client.post("/api/connect/bind", json={"handle": consent}).status_code == 204
    body = {
        "handle": consent,
        "client_id": app,
        "redirect_uri": CALLBACK,
        "scopes": ["training:read"] if scopes is None else scopes,
    } | changes
    return client.post("/api/connect/approve", json=body)


def exchange(client: TestClient, app: str, code: str, **changes: str) -> Response:
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": app,
        "redirect_uri": CALLBACK,
        "code_verifier": VERIFIER,
        "resource": MCP,
    } | changes
    return client.post("/oauth/token", data=form, headers={"cf-connecting-ip": ADDRESS})


def refresh(client: TestClient, app: str, token: str, **changes: str) -> Response:
    form = {"grant_type": "refresh_token", "refresh_token": token, "client_id": app} | changes
    return client.post("/oauth/token", data=form, headers={"cf-connecting-ip": ADDRESS})


def mint(engine: Engine, scopes: list[str], user: int = OWNER, resource: str = MCP) -> str:
    """An access token straight from the services, skipping the consent page: for tests of
    what a token may read, not of how it was approved."""
    now = datetime.now(UTC)
    with session_scope(make_session_factory(engine)) as shared:
        app = OAuthClient(
            client_id=mcp_tokens.new_secret(),
            name="Claude",
            redirect_uris=[CALLBACK],
            client_hash="0" * 64,
            expires_at=now,
            approved_at=now,
        )
        shared.add(app)
        shared.flush()
        client_row, public_id = app.id, app.client_id
    with session_scope(make_session_factory(engine, user_id=user)) as bound:
        connection = mcp_tokens.create_connection(
            bound, client_row, "Claude", CALLBACK, scopes, None, now
        )
        code = mcp_tokens.issue_code(bound, connection, CALLBACK, CHALLENGE.decode(), now)
    with session_scope(make_session_factory(engine)) as shared:
        tokens = mcp_tokens.exchange_code(
            shared, code, public_id, CALLBACK, VERIFIER, None, resource, now
        )
    assert isinstance(tokens, mcp_tokens.Tokens)
    return tokens.access_token


@contextmanager
def no_cookies(client: TestClient) -> Iterator[None]:
    """As the AI app's servers call: without the person's browser cookies."""
    saved = dict(client.cookies)
    client.cookies.clear()
    try:
        yield
    finally:
        for name, value in saved.items():
            client.cookies.set(name, value)


def connect(
    client: TestClient, engine: Engine, scopes: list[str] | None = None
) -> tuple[str, dict[str, Any]]:
    """The whole flow, from a passkey sign-in: the app's client id and its token answer."""
    device = add_passkey(client, engine)
    sign_in_with_passkey(client, device)
    app = client_id(client)
    approved = approve(client, handle(client, app), app, scopes)
    assert approved.status_code == 200, approved.text
    code = query(approved.json()["redirect"])["code"]
    with no_cookies(client):
        tokens = exchange(client, app, code)
    assert tokens.status_code == 200, tokens.text
    answer: dict[str, Any] = tokens.json()
    return app, answer
