"""GET /api/notices and POST /api/notices/read (ADR-0087): each person's own, until seen."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import PlanNotice
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth
from training_coach.services.users import OWNER


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as signed_in:
        with make_session_factory(engine, user_id=OWNER)() as bound:
            token = auth.create_link(bound, datetime.now(UTC))
            bound.commit()
        assert signed_in.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield signed_in


def test_notices_need_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as stranger:
        assert stranger.get("/api/notices").status_code == 401
        assert stranger.post("/api/notices/read", json={"ids": [1]}).status_code == 401


def test_a_notice_shows_until_got_it(client: TestClient, engine: Engine) -> None:
    assert client.get("/api/notices").json() == []
    with session_scope(make_session_factory(engine, user_id=OWNER)) as bound:
        bound.add(PlanNotice(text="Pull-up is now called Bar pull."))
    (shown,) = client.get("/api/notices").json()
    assert shown["text"] == "Pull-up is now called Bar pull."
    assert client.post("/api/notices/read", json={"ids": [shown["id"]]}).status_code == 204
    assert client.get("/api/notices").json() == []
