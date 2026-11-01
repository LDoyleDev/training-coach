"""The country of residence on Account (ADR-0085 layer 3): from the list, or refused."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth
from training_coach.services.users import OWNER

PATH = "/api/account/residence"


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
            token = auth.create_link(bound, datetime.now(UTC))
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


def _stored(engine: Engine) -> str | None:
    with session_scope(make_session_factory(engine)) as shared:
        return shared.get_one(User, OWNER).country


def test_nobody_has_said_yet_and_the_choices_are_the_list(signed_in: TestClient) -> None:
    found = signed_in.get(PATH).json()
    assert found["country"] is None
    assert len(found["choices"]) == 37
    assert {"DE", "IE", "NO", "AX"} <= set(found["choices"])


def test_a_country_on_the_list_is_kept(signed_in: TestClient, engine: Engine) -> None:
    answer = signed_in.put(PATH, json={"country": "ie"})
    assert answer.status_code == 200
    assert answer.json()["country"] == "IE"
    assert _stored(engine) == "IE"


@pytest.mark.parametrize("country", ["GB", "CH", "US", "XX"])
def test_somewhere_else_is_refused_with_the_reason(
    signed_in: TestClient, engine: Engine, country: str
) -> None:
    signed_in.put(PATH, json={"country": "DE"})
    answer = signed_in.put(PATH, json={"country": country})
    assert answer.status_code == 422
    assert "only for people living in the EU or EEA" in answer.json()["detail"]
    assert _stored(engine) == "DE"  # unchanged


def test_it_needs_a_signed_in_browser(client: TestClient) -> None:
    assert client.get(PATH).status_code == 401
    assert client.put(PATH, json={"country": "DE"}).status_code == 401
