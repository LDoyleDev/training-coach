""" "Last seen in Europe" (ADR-0085 layer 4): only the person's own signed-in visit from a listed
country moves it, at most once an hour."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth
from training_coach.services.users import OWNER

LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)
TUNNEL = ("172.17.0.1", 50000)


def _client(engine: Engine, peer: tuple[str, int] = TUNNEL) -> TestClient:
    settings = Settings(environment="test", database_url=str(engine.url))
    return TestClient(create_app(settings), base_url="https://testserver", client=peer)


def _last_seen(engine: Engine, value: datetime | None = None) -> datetime:
    with session_scope(make_session_factory(engine)) as shared:
        user = shared.get(User, OWNER)
        assert user is not None
        if value is not None:
            user.last_seen_in_europe = value
        return user.last_seen_in_europe


def _sign_in(client: TestClient, engine: Engine) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        token = auth.create_link(bound, datetime.now(UTC))
    assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    with _client(engine) as client:
        _sign_in(client, engine)
        _last_seen(engine, LONG_AGO)
        yield client


def test_a_signed_in_visit_from_a_listed_country_is_recorded(
    signed_in: TestClient, engine: Engine
) -> None:
    assert signed_in.get("/api/auth/me", headers={"CF-IPCountry": "NO"}).status_code == 200
    assert datetime.now(UTC) - _last_seen(engine) < timedelta(minutes=1)


def test_it_is_written_at_most_once_an_hour(signed_in: TestClient, engine: Engine) -> None:
    recent = datetime.now(UTC) - timedelta(minutes=30)
    _last_seen(engine, recent)
    signed_in.get("/api/auth/me", headers={"CF-IPCountry": "DE"})
    assert _last_seen(engine) == recent


@pytest.mark.parametrize("headers", [{}, {"CF-IPCountry": ""}])
def test_a_visit_without_a_country_does_not_count(
    signed_in: TestClient, engine: Engine, headers: dict[str, str]
) -> None:
    """Let through (the app fails open), but not proof of being in Europe."""
    assert signed_in.get("/api/auth/me", headers=headers).status_code == 200
    assert _last_seen(engine) == LONG_AGO


def test_signed_out_requests_do_not_count(engine: Engine) -> None:
    _last_seen(engine, LONG_AGO)
    with _client(engine) as client:
        assert client.get("/api/auth/me", headers={"CF-IPCountry": "DE"}).status_code == 401
        client.get("/signin", headers={"CF-IPCountry": "DE"})
    assert _last_seen(engine) == LONG_AGO


def test_a_country_named_by_an_untrusted_peer_does_not_count(engine: Engine) -> None:
    with _client(engine, ("203.0.113.9", 50000)) as client:
        _sign_in(client, engine)
        _last_seen(engine, LONG_AGO)
        assert client.get("/api/auth/me", headers={"CF-IPCountry": "DE"}).status_code == 200
    assert _last_seen(engine) == LONG_AGO


def test_only_the_signed_in_persons_date_moves(engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2, last_seen_in_europe=LONG_AGO))
    with _client(engine) as client:
        with session_scope(make_session_factory(engine, user_id=2)) as bound:
            token = auth.create_link(bound, datetime.now(UTC))
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        _last_seen(engine, LONG_AGO)
        client.get("/api/auth/me", headers={"CF-IPCountry": "DE"})
    assert _last_seen(engine) == LONG_AGO
    with session_scope(make_session_factory(engine)) as shared:
        other = shared.get(User, 2)
        assert other is not None
        assert other.last_seen_in_europe > LONG_AGO
