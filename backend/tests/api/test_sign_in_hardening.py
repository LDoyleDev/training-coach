"""Sign-in hardening (ADR-0040): links once a passkey exists, recovery, fresh sign-in for passkey
changes, and the Telegram alerts."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from tests.api.test_passkeys import ORIGIN, RP_ID, _options, _passkeys, _register, _sign_in
from tests.passkey_device import Device
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Passkey, WebSession
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.services import auth
from training_coach.services.users import OWNER


@pytest.fixture
def sent() -> list[str]:
    return []


@pytest.fixture
def client(engine: Engine, sent: list[str]) -> Iterator[TestClient]:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(
        create_app(settings), base_url=ORIGIN, client=("172.17.0.1", 50000)
    ) as test_client:

        async def notify(text: str) -> None:
            sent.append(text)

        test_client.app.state.notify = notify  # type: ignore[attr-defined]  # a FastAPI app
        yield test_client


def _link(engine: Engine, purpose: str = auth.START) -> str:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        return auth.create_link(bound, datetime.now(UTC), purpose)


def _redeem(client: TestClient, token: str) -> int:
    return client.post("/api/auth/redeem", json={"token": token}).status_code


def _with_passkey(client: TestClient, engine: Engine) -> Device:
    assert _redeem(client, _link(engine)) == 204
    device = Device(ORIGIN, RP_ID)
    assert _register(client, device) == 204
    return device


def test_a_link_signs_in_and_alerts(client: TestClient, engine: Engine, sent: list[str]) -> None:
    assert _redeem(client, _link(engine)) == 204
    assert len(sent) == 1
    assert sent[0].startswith("New sign-in to Training Coach with a link from the bot, on ")


def test_once_a_passkey_exists_a_link_alone_no_longer_signs_in(
    client: TestClient, engine: Engine, sent: list[str]
) -> None:
    device = _with_passkey(client, engine)
    client.cookies.clear()
    token = _link(engine)
    assert _redeem(client, token) == 403
    assert client.get("/api/auth/me").status_code == 401
    assert _redeem(client, token) == 401  # used up all the same
    assert _sign_in(client, device) == 204  # the fingerprint does
    assert sent[-1].startswith("New sign-in to Training Coach with your passkey, on ")


def test_recovery_signs_out_everyone_else_and_removes_every_passkey(
    client: TestClient, engine: Engine, sent: list[str]
) -> None:
    _with_passkey(client, engine)
    other = client.cookies.get("__Host-tc_session")
    client.cookies.clear()
    assert _redeem(client, _link(engine, auth.RECOVER)) == 204
    assert client.get("/api/auth/me").json() == {"user_id": OWNER}
    assert _passkeys(engine) == []
    with make_session_factory(engine)() as shared:
        live = shared.scalars(
            select(WebSession.token_hash).where(WebSession.ended_at.is_(None)),
            execution_options={ALL_USERS: True},
        ).all()
    assert live == [auth.hash_token(client.cookies.get("__Host-tc_session") or "")]
    assert auth.hash_token(other or "") not in live
    assert "Recovery sign-in" in sent[-1]
    assert "every passkey removed" in sent[-1]


def test_adding_or_removing_a_passkey_needs_a_recent_sign_in(
    client: TestClient, engine: Engine, sent: list[str]
) -> None:
    with time_machine.travel(datetime.now(UTC), tick=False) as clock:
        _with_passkey(client, engine)
        assert sent[-1].startswith("A passkey was added to Training Coach on ")
        clock.shift(timedelta(minutes=11))
        assert client.post("/api/auth/passkeys/register/options").status_code == 403
        (key,) = _passkeys(engine)
        assert client.delete(f"/api/account/passkeys/{key.id}").status_code == 403
        assert len(_passkeys(engine)) == 1


def test_a_fresh_sign_in_may_remove_a_passkey_and_it_alerts(
    client: TestClient, engine: Engine, sent: list[str]
) -> None:
    _with_passkey(client, engine)
    (key,) = _passkeys(engine)
    assert client.delete(f"/api/account/passkeys/{key.id}").status_code == 204
    assert sent[-1] == "A passkey was removed from Training Coach."


def test_signing_out_a_device_alerts(client: TestClient, engine: Engine, sent: list[str]) -> None:
    assert _redeem(client, _link(engine)) == 204
    with make_session_factory(engine, user_id=OWNER)() as bound:
        cookie = auth.start_session(bound, OWNER, datetime.now(UTC), "Old laptop")
        bound.commit()
        old = bound.scalars(
            select(WebSession.id).where(WebSession.token_hash == auth.hash_token(cookie))
        ).one()
    assert client.delete(f"/api/account/devices/{old}").status_code == 204
    assert sent[-1] == "A device was signed out of Training Coach."


def test_without_the_bot_alerts_are_only_logged(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as quiet:
        assert quiet.app.state.notify is None  # type: ignore[attr-defined]  # a FastAPI app
        assert _redeem(quiet, _link(engine)) == 204


def test_an_unknown_purpose_never_signs_in_without_a_passkey(
    client: TestClient, engine: Engine
) -> None:
    _with_passkey(client, engine)
    client.cookies.clear()
    assert _redeem(client, _link(engine, "other")) == 403
    with make_session_factory(engine)() as shared:
        assert shared.scalars(select(Passkey.id), execution_options={ALL_USERS: True}).all()
    assert _options(client, "/api/auth/passkeys/sign-in/options")["rpId"] == RP_ID
