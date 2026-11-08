"""/api/readiness and Today's note on hard days (ADR-0085): the server records only when the
health questions were answered and which version, never the answers."""

import io
import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import (
    FitnessTestDay,
    PlanState,
    ReadinessCheck,
    SessionTemplate,
    Workout,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import WorkoutStatus
from training_coach.domain.queue import local_date
from training_coach.domain.readiness import DUE_NOTE, HARD_NOTE, RENEW, VERSION
from training_coach.services import auth
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
ANSWERED = {"version": VERSION}


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


def _today_is(engine: Engine, slug: str) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        template = mine.scalars(select(SessionTemplate).where(SessionTemplate.slug == slug)).one()
        mine.scalars(select(PlanState)).one().next_template_id = template.id


def _rows(engine: Engine) -> list[ReadinessCheck]:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        rows = list(mine.scalars(select(ReadinessCheck)))
        mine.expunge_all()
    return rows


def test_unanswered_is_due(signed_in: TestClient) -> None:
    assert signed_in.get("/api/readiness").json() == {
        "version": VERSION,
        "due": True,
        "answered_at": None,
        "ask_again_after": None,
    }


def test_answering_records_only_when_and_which_version(
    signed_in: TestClient, engine: Engine
) -> None:
    saved = signed_in.put("/api/readiness", json=ANSWERED).json()
    assert saved["due"] is False
    assert saved["ask_again_after"] is not None
    assert signed_in.get("/api/readiness").json() == saved
    signed_in.put("/api/readiness", json=ANSWERED)
    (row,) = _rows(engine)  # replaced, not added
    assert row.version == VERSION
    # Nowhere to put an answer (ADR-0085).
    assert set(ReadinessCheck.__table__.columns.keys()) == {
        "id",
        "user_id",
        "version",
        "answered_at",
    }


def test_answers_sent_anyway_are_never_kept(signed_in: TestClient, engine: Engine) -> None:
    sent = {"version": VERSION, "answers": {"chest_pain": True}}
    assert signed_in.put("/api/readiness", json=sent).status_code == 200
    exported = signed_in.get("/api/account/export")
    assert b"chest_pain" not in zipfile.ZipFile(io.BytesIO(exported.content)).read("data.json")
    assert len(_rows(engine)) == 1


def test_an_older_version_of_the_questions_is_refused(signed_in: TestClient) -> None:
    """A page loaded before a release asked the old questions: it reloads and asks again."""
    assert signed_in.put("/api/readiness", json={"version": VERSION - 1}).status_code == 409
    assert signed_in.get("/api/readiness").json()["due"] is True


def test_after_a_year_the_questions_are_asked_again(signed_in: TestClient, engine: Engine) -> None:
    signed_in.put("/api/readiness", json=ANSWERED)
    # Answered back then (moving the clock instead would also end this sign-in).
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        row = mine.scalars(select(ReadinessCheck)).one()
        row.answered_at = datetime.now(UTC) - RENEW - timedelta(days=1)
    view = signed_in.get("/api/readiness").json()
    assert (view["due"], view["answered_at"]) == (True, None)


def test_readiness_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/readiness").status_code == 401
        assert stranger.put("/api/readiness", json=ANSWERED).status_code == 401


def test_a_hard_day_asks_for_the_questions_then_gives_the_general_line(
    signed_in: TestClient, engine: Engine
) -> None:
    _today_is(engine, "hiit")
    assert signed_in.get("/api/session/today").json()["readiness_note"] == DUE_NOTE
    signed_in.put("/api/readiness", json=ANSWERED)
    assert signed_in.get("/api/session/today").json()["readiness_note"] == HARD_NOTE


def test_an_easy_day_says_nothing(signed_in: TestClient, engine: Engine) -> None:
    _today_is(engine, "zone2")
    today = signed_in.get("/api/session/today").json()
    assert today["session"] is not None
    assert today["readiness_note"] is None


def test_a_test_day_is_a_hard_day_even_with_nothing_left_to_train(
    signed_in: TestClient, engine: Engine
) -> None:
    """Day 2 of the tests is due today (day 1 was yesterday): hard, whatever the session."""
    _today_is(engine, "zone2")  # an easy session
    today = local_date(datetime.now(UTC), Settings().tz)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        mine.add(
            FitnessTestDay(
                local_date=today - timedelta(days=1),
                day=1,
                time_of_day="morning",
                fed=True,
                slept_well=True,
                results=[],
                token="d" * 20,
            )
        )
    view = signed_in.get("/api/session/today").json()
    assert view["test_day"] is not None
    assert view["readiness_note"] == DUE_NOTE
    template = view["session"]["template_id"]
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        mine.add(Workout(local_date=today, template_id=template, status=WorkoutStatus.REST))
    view = signed_in.get("/api/session/today").json()
    assert view["session"] is None  # today's session is done
    assert view["readiness_note"] == DUE_NOTE


def test_the_export_says_when_and_nothing_more(signed_in: TestClient) -> None:
    signed_in.put("/api/readiness", json=ANSWERED)
    exported = signed_in.get("/api/account/export")  # this client signed in just now
    zipped = zipfile.ZipFile(io.BytesIO(exported.content))
    (row,) = json.loads(zipped.read("data.json"))["tables"]["readiness_checks"]
    assert row["version"] == VERSION
    assert "answers" not in row
