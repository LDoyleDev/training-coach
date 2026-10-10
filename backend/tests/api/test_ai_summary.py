"""GET /api/account/ai-summary: my training as Markdown for my own AI (ADR-0047)."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import auth
from training_coach.services.ai_summary import GUIDE_URL
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


def test_the_summary_is_markdown_linking_the_guide(signed_in: TestClient) -> None:
    answer = signed_in.get("/api/account/ai-summary")
    assert answer.status_code == 200
    assert answer.headers["content-type"].startswith("text/markdown")
    assert "no-store" in answer.headers["cache-control"]
    assert GUIDE_URL in answer.text
    today = local_date(datetime.now(UTC), Settings().tz)
    assert f"to {today.isoformat()}" in answer.text  # the last 4 weeks by default


def test_measurements_only_when_asked(signed_in: TestClient) -> None:
    assert signed_in.put("/api/body", json={"values": {"waist": 84.5}}).is_success
    assert "84.5" not in signed_in.get("/api/account/ai-summary").text
    shared = signed_in.get("/api/account/ai-summary", params={"body": "true", "period": "all"})
    assert "Waist: 84.5 cm" in shared.text
    assert "Period: everything" in shared.text


def test_an_unknown_period_is_refused(signed_in: TestClient) -> None:
    assert signed_in.get("/api/account/ai-summary", params={"period": "2y"}).status_code == 422


def test_the_summary_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/account/ai-summary").status_code == 401
