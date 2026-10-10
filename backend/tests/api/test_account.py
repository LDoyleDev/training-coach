"""The account page's sign-ins (ADR-0036): passkeys and browsers, listed and removable."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.passkey_device import Device
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Passkey, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
PEER = ("172.17.0.1", 50000)


@pytest.fixture
def app(engine: Engine) -> FastAPI:
    return create_app(Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN))


def _browser(app: FastAPI, engine: Engine, user: int = OWNER, agent: str = "Phone") -> TestClient:
    """A browser signed in with a fresh bot link."""
    with make_session_factory(engine, user_id=user)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    client = TestClient(app, base_url=ORIGIN, client=PEER, headers={"user-agent": agent})
    assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
    return client


@pytest.fixture
def phone(app: FastAPI, engine: Engine) -> Iterator[TestClient]:
    with _browser(app, engine) as client:
        yield client


def _sign_ins(client: TestClient) -> dict[str, Any]:
    response = client.get("/api/account/sign-ins")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


def test_sign_ins_list_this_and_other_browsers(
    app: FastAPI, engine: Engine, phone: TestClient
) -> None:
    with _browser(app, engine, agent="Laptop"):
        devices = _sign_ins(phone)["devices"]
    assert sorted(d["label"] for d in devices) == ["Laptop", "Phone"]
    assert [d["label"] for d in devices if d["current"]] == ["Phone"]


def test_signing_out_another_browser_ends_it(
    app: FastAPI, engine: Engine, phone: TestClient
) -> None:
    with _browser(app, engine, agent="Lost phone") as lost:
        lost_id = next(d["id"] for d in _sign_ins(phone)["devices"] if d["label"] == "Lost phone")
        assert phone.delete(f"/api/account/devices/{lost_id}").status_code == 204
        assert lost.get("/api/auth/me").status_code == 401
    assert [d["label"] for d in _sign_ins(phone)["devices"]] == ["Phone"]
    assert phone.delete(f"/api/account/devices/{lost_id}").status_code == 404  # already ended


def test_a_removed_passkey_no_longer_signs_in(phone: TestClient) -> None:
    device = Device(ORIGIN, "coach.example.com")
    options = json.loads(phone.post("/api/auth/passkeys/register/options").text)
    phone.post("/api/auth/passkeys/register", json={"credential": device.register(options)})
    (key,) = _sign_ins(phone)["passkeys"]
    assert key["name"] == "Phone"
    assert phone.delete(f"/api/account/passkeys/{key['id']}").status_code == 204
    assert _sign_ins(phone)["passkeys"] == []
    phone.cookies.delete("__Host-tc_session")
    options = json.loads(phone.post("/api/auth/passkeys/sign-in/options").text)
    answer = device.sign_in(options)
    assert phone.post("/api/auth/passkeys/sign-in", json={"credential": answer}).status_code == 401


def test_another_persons_keys_and_browsers_are_not_there(
    app: FastAPI, engine: Engine, phone: TestClient
) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
    with _browser(app, engine, user=2, agent="Their phone") as them:
        with session_scope(make_session_factory(engine, user_id=2)) as theirs:
            key = Passkey(credential_id="theirs", public_key=b"k", sign_count=0, name="Theirs")
            theirs.add(key)
            theirs.flush()
            key_id = key.id
        their_device = _sign_ins(them)["devices"][0]["id"]
        assert phone.delete(f"/api/account/passkeys/{key_id}").status_code == 404
        assert phone.delete(f"/api/account/devices/{their_device}").status_code == 404
        assert them.get("/api/auth/me").json() == {"user_id": 2}
    assert [d["label"] for d in _sign_ins(phone)["devices"]] == ["Phone"]


def test_the_account_needs_a_signed_in_browser(app: FastAPI) -> None:
    with TestClient(app, base_url=ORIGIN) as stranger:
        assert stranger.get("/api/account/sign-ins").status_code == 401
        assert stranger.delete("/api/account/passkeys/1").status_code == 401
        assert stranger.delete("/api/account/devices/1").status_code == 401
