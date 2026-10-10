"""Passkeys end to end (ADR-0036): a software device registers while signed in, then signs in
with its fingerprint; every way a stranger or a replay could get in is refused."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete, select

from tests.passkey_device import Device
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Passkey, PasskeyChallenge
from training_coach.db.session import ALL_USERS, make_session_factory
from training_coach.services import auth, passkeys
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
RP_ID = "coach.example.com"


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    # The tunnel reaches the app from a private address (the Docker bridge).
    with TestClient(
        create_app(settings), base_url=ORIGIN, client=("172.17.0.1", 50000)
    ) as test_client:
        yield test_client


def _signed_in(client: TestClient, engine: Engine) -> None:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204


def _options(client: TestClient, path: str) -> dict[str, Any]:
    response = client.post(path)
    assert response.status_code == 200
    options: dict[str, Any] = json.loads(response.text)
    return options


def _register(client: TestClient, device: Device) -> int:
    options = _options(client, "/api/auth/passkeys/register/options")
    return client.post(
        "/api/auth/passkeys/register", json={"credential": device.register(options)}
    ).status_code


def _sign_in(client: TestClient, device: Device, origin: str | None = None) -> int:
    client.cookies.delete("__Host-tc_session")
    options = _options(client, "/api/auth/passkeys/sign-in/options")
    return client.post(
        "/api/auth/passkeys/sign-in", json={"credential": device.sign_in(options, origin)}
    ).status_code


def _passkeys(engine: Engine) -> list[Passkey]:
    with make_session_factory(engine)() as shared:
        return list(shared.scalars(select(Passkey), execution_options={ALL_USERS: True}))


def test_add_a_passkey_then_sign_in_with_it(client: TestClient, engine: Engine) -> None:
    _signed_in(client, engine)
    device = Device(ORIGIN, RP_ID)
    options = _options(client, "/api/auth/passkeys/register/options")
    assert options["rp"]["id"] == RP_ID
    assert options["authenticatorSelection"]["userVerification"] == "required"
    assert options["authenticatorSelection"]["residentKey"] == "required"
    added = client.post(
        "/api/auth/passkeys/register", json={"credential": device.register(options)}
    )
    assert added.status_code == 204
    (stored,) = _passkeys(engine)
    assert stored.user_id == OWNER

    assert _sign_in(client, device) == 204
    assert client.get("/api/auth/me").json() == {"user_id": OWNER}
    assert _passkeys(engine)[0].sign_count == 1


def test_only_a_signed_in_person_can_add_a_passkey(client: TestClient) -> None:
    assert client.post("/api/auth/passkeys/register/options").status_code == 401
    assert client.post("/api/auth/passkeys/register", json={"credential": {}}).status_code == 401


def test_a_device_that_did_not_verify_the_user_is_refused(
    client: TestClient, engine: Engine
) -> None:
    _signed_in(client, engine)
    tap_only = Device(ORIGIN, RP_ID, user_verified=False)
    assert _register(client, tap_only) == 400
    assert _passkeys(engine) == []
    good = Device(ORIGIN, RP_ID)
    assert _register(client, good) == 204
    good.user_verified = False
    assert _sign_in(client, good) == 401


def test_an_unknown_passkey_or_another_site_is_refused(client: TestClient, engine: Engine) -> None:
    _signed_in(client, engine)
    device = Device(ORIGIN, RP_ID)
    assert _register(client, device) == 204
    assert _sign_in(client, Device(ORIGIN, RP_ID)) == 401  # never registered
    assert _sign_in(client, device, origin="https://evil.example.com") == 401
    assert client.get("/api/auth/me").status_code == 401


def test_an_answer_cannot_be_replayed(client: TestClient, engine: Engine) -> None:
    _signed_in(client, engine)
    device = Device(ORIGIN, RP_ID)
    assert _register(client, device) == 204
    client.cookies.delete("__Host-tc_session")
    options = _options(client, "/api/auth/passkeys/sign-in/options")
    handle = client.cookies.get("tc_passkey")
    answer = device.sign_in(options)
    assert client.post("/api/auth/passkeys/sign-in", json={"credential": answer}).status_code == 204
    client.cookies.delete("__Host-tc_session")
    client.cookies.set("tc_passkey", handle or "", path="/api/auth/passkeys")  # the old challenge
    assert client.post("/api/auth/passkeys/sign-in", json={"credential": answer}).status_code == 401


def test_a_challenge_expires_after_five_minutes(client: TestClient, engine: Engine) -> None:
    _signed_in(client, engine)
    device = Device(ORIGIN, RP_ID)
    assert _register(client, device) == 204
    client.cookies.delete("__Host-tc_session")
    start = datetime.now(UTC)
    with time_machine.travel(start, tick=False):
        options = _options(client, "/api/auth/passkeys/sign-in/options")
    handle = client.cookies.get("tc_passkey") or ""
    with time_machine.travel(start + timedelta(minutes=5, seconds=1), tick=False):
        # The browser drops the cookie too; send it anyway: the server must refuse on its own.
        client.cookies.set("tc_passkey", handle, path="/api/auth/passkeys")
        late = client.post(
            "/api/auth/passkeys/sign-in", json={"credential": device.sign_in(options)}
        )
    assert late.status_code == 401


def test_a_sign_in_challenge_cannot_add_a_passkey(client: TestClient, engine: Engine) -> None:
    _signed_in(client, engine)
    options = _options(client, "/api/auth/passkeys/sign-in/options")  # the wrong ceremony
    fake = {**options, "rp": {"id": RP_ID}, "user": {"id": "MQ"}}
    answer = Device(ORIGIN, RP_ID).register(fake)
    assert (
        client.post("/api/auth/passkeys/register", json={"credential": answer}).status_code == 400
    )
    assert _passkeys(engine) == []


def test_without_a_challenge_or_a_public_url_nothing_starts(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url=ORIGIN) as no_url:
        assert no_url.post("/api/auth/passkeys/sign-in/options").status_code == 503
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as fresh:
        assert fresh.post("/api/auth/passkeys/sign-in", json={"credential": {}}).status_code == 400


def test_unanswered_challenges_are_cleared(client: TestClient, engine: Engine) -> None:
    start = datetime.now(UTC)
    with time_machine.travel(start, tick=False):
        _options(client, "/api/auth/passkeys/sign-in/options")
    with time_machine.travel(start + timedelta(minutes=6), tick=False):
        _options(client, "/api/auth/passkeys/sign-in/options")
    with make_session_factory(engine)() as shared:
        assert len(shared.scalars(select(PasskeyChallenge)).all()) == 1


def test_a_garbled_answer_is_refused(client: TestClient, engine: Engine) -> None:
    _options(client, "/api/auth/passkeys/sign-in/options")
    junk = {"id": "x", "rawId": "x", "type": "public-key", "response": {}}
    assert client.post("/api/auth/passkeys/sign-in", json={"credential": junk}).status_code == 401


def test_the_party_comes_from_the_parsed_public_url() -> None:
    assert passkeys.Party.from_url(ORIGIN) == passkeys.Party(ORIGIN, RP_ID)
    assert passkeys.Party.from_url(ORIGIN + "/") == passkeys.Party(ORIGIN, RP_ID)
    local = passkeys.Party.from_url("http://localhost:5173/app")
    assert local == passkeys.Party("http://localhost:5173", "localhost")
    with pytest.raises(ValueError, match="no host"):
        passkeys.Party.from_url("https://")
    with pytest.raises(ValueError, match="https"):
        passkeys.Party.from_url("http://coach.example.com")


def test_registering_needs_a_session_bound_to_someone(engine: Engine) -> None:
    with make_session_factory(engine)() as unbound, pytest.raises(PermissionError):
        passkeys.registration(unbound, passkeys.Party(ORIGIN, RP_ID), datetime.now(UTC))


def test_a_key_registered_already_is_refused_not_an_error(
    client: TestClient, engine: Engine
) -> None:
    """Browsers exclude known keys, but a re-submitted one must be a 400 (review of #123)."""
    _signed_in(client, engine)
    device = Device(ORIGIN, RP_ID)
    assert _register(client, device) == 204
    assert _register(client, device) == 400
    assert len(_passkeys(engine)) == 1


@pytest.mark.parametrize("field", ["clientDataJSON", "authenticatorData", "signature"])
def test_malformed_fields_are_a_refusal_not_an_error(
    client: TestClient, engine: Engine, field: str
) -> None:
    _signed_in(client, engine)
    device = Device(ORIGIN, RP_ID)
    assert _register(client, device) == 204
    client.cookies.delete("__Host-tc_session")
    options = _options(client, "/api/auth/passkeys/sign-in/options")
    answer = device.sign_in(options)
    answer["response"][field] = "%%% not base64 %%%"
    assert client.post("/api/auth/passkeys/sign-in", json={"credential": answer}).status_code == 401


def _open(client: TestClient, ip: str) -> int:
    path = "/api/auth/passkeys/sign-in/options"
    return client.post(path, headers={"CF-Connecting-IP": ip}).status_code


def test_a_stranger_cannot_use_up_the_owners_sign_ins(client: TestClient) -> None:
    """Capped per client (review of #123): one address filling its quota leaves others free."""
    for _ in range(passkeys.MAX_OPEN_PER_CLIENT):
        assert _open(client, "203.0.113.9") == 200
    assert _open(client, "203.0.113.9") == 429
    assert _open(client, "198.51.100.7") == 200  # the owner, elsewhere


def test_open_sign_ins_are_capped_overall(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(passkeys, "MAX_OPEN_SIGN_INS", 3)
    for n in range(3):
        assert _open(client, f"203.0.113.{n}") == 200
    assert _open(client, "198.51.100.7") == 429


def test_a_refusal_also_clears_the_challenge_cookie(client: TestClient) -> None:
    _options(client, "/api/auth/passkeys/sign-in/options")
    refused = client.post("/api/auth/passkeys/sign-in", json={"credential": {"id": "x"}})
    assert refused.status_code == 401
    assert 'tc_passkey=""' in refused.headers["set-cookie"]


def test_a_forwarded_address_counts_only_from_the_tunnel(engine: Engine) -> None:
    """A caller reaching the app directly can't dodge the cap with a new header each time."""
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    # A public peer, a home-network peer (not the tunnel's side) and a non-IP peer.
    for peer in ("8.8.8.8", "192.168.1.20", "testclient"):
        with TestClient(create_app(settings), base_url=ORIGIN, client=(peer, 50000)) as direct:
            for n in range(passkeys.MAX_OPEN_PER_CLIENT):
                assert _open(direct, f"198.51.100.{n}") == 200
            assert _open(direct, "198.51.100.99") == 429, peer  # all counted as the peer
        with make_session_factory(engine)() as shared:
            shared.execute(delete(PasskeyChallenge))
            shared.commit()


def test_an_unusable_public_url_is_not_set_up_not_an_error(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    settings.public_url = "http://coach.example.com"  # bypassing the settings check
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/passkeys/sign-in/options").status_code == 503


def test_a_garbled_registration_is_refused_not_an_error(client: TestClient, engine: Engine) -> None:
    _signed_in(client, engine)
    options = _options(client, "/api/auth/passkeys/register/options")
    answer = Device(ORIGIN, RP_ID).register(options)
    answer["response"]["attestationObject"] = "%%% not cbor %%%"
    refused = client.post("/api/auth/passkeys/register", json={"credential": answer})
    assert refused.status_code == 400
    assert 'tc_passkey=""' in refused.headers["set-cookie"]


def test_the_same_key_saved_twice_at_once_is_refused(engine: Engine) -> None:
    """Two registrations racing past the duplicate check: the unique id decides (review)."""
    party = passkeys.Party(ORIGIN, RP_ID)
    device = Device(ORIGIN, RP_ID)
    now = datetime.now(UTC)
    with make_session_factory(engine, user_id=OWNER)() as first:
        ceremony = passkeys.registration(first, party, now)
        answer = device.register(json.loads(ceremony.options))
        first.commit()
    with make_session_factory(engine, user_id=OWNER)() as racing:
        racing.add(
            Passkey(credential_id=answer["id"], public_key=b"x", sign_count=0, name="other tab")
        )
        racing.commit()
    with make_session_factory(engine, user_id=OWNER)() as second:
        assert not passkeys.register(second, party, ceremony.handle, answer, "phone", now)
