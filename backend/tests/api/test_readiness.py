"""/api/readiness and Today's readiness note (ADR-0046)."""

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
    ReadinessAnswers,
    SessionTemplate,
    Workout,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import WorkoutStatus
from training_coach.domain.queue import local_date
from training_coach.domain.readiness import DOCTOR_NOTE, DUE_NOTE, KEYS, RENEW
from training_coach.services import auth
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
ALL_NO = dict.fromkeys(KEYS, False)


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


def test_unanswered_lists_the_questions_and_is_due(signed_in: TestClient) -> None:
    view = signed_in.get("/api/readiness").json()
    assert view["status"] == "due"
    assert {q["key"] for q in view["questions"]} == KEYS
    assert view["answers"] is None


def test_answers_are_kept_and_say_what_they_mean(signed_in: TestClient) -> None:
    saved = signed_in.put("/api/readiness", json={"answers": ALL_NO})
    assert saved.json() == {"status": "clear"}
    view = signed_in.get("/api/readiness").json()
    assert (view["status"], view["answers"]) == ("clear", ALL_NO)
    assert view["ask_again_after"] is not None
    yes = {**ALL_NO, "chest_pain": True}
    assert signed_in.put("/api/readiness", json={"answers": yes}).json() == {"status": "see_doctor"}
    assert signed_in.get("/api/readiness").json()["answers"] == yes  # replaced, not added


@pytest.mark.parametrize(
    "answers",
    [{}, {"heart": False}, {**ALL_NO, "extra": False}],
    ids=["none", "some", "an-unknown-one"],
)
def test_every_question_needs_an_answer(signed_in: TestClient, answers: dict[str, bool]) -> None:
    assert signed_in.put("/api/readiness", json={"answers": answers}).status_code == 422
    assert signed_in.get("/api/readiness").json()["status"] == "due"


def test_after_six_months_the_questions_are_asked_again(
    signed_in: TestClient, engine: Engine
) -> None:
    signed_in.put("/api/readiness", json={"answers": ALL_NO})
    # Answered back then (moving the clock instead would also end this sign-in).
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        row = mine.scalars(select(ReadinessAnswers)).one()
        row.answered_at = datetime.now(UTC) - RENEW - timedelta(days=1)
    view = signed_in.get("/api/readiness").json()
    assert (view["status"], view["answers"]) == ("due", None)


def test_readiness_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/readiness").status_code == 401
        assert stranger.put("/api/readiness", json={"answers": ALL_NO}).status_code == 401


def test_a_hard_day_asks_for_the_answers_then_advises(
    signed_in: TestClient, engine: Engine
) -> None:
    _today_is(engine, "hiit")
    assert signed_in.get("/api/session/today").json()["readiness_note"] == DUE_NOTE
    signed_in.put("/api/readiness", json={"answers": {**ALL_NO, "heart": True}})
    assert signed_in.get("/api/session/today").json()["readiness_note"] == DOCTOR_NOTE
    signed_in.put("/api/readiness", json={"answers": ALL_NO})
    assert signed_in.get("/api/session/today").json()["readiness_note"] is None


def test_an_easy_day_says_nothing(signed_in: TestClient, engine: Engine) -> None:
    _today_is(engine, "zone2")
    signed_in.put("/api/readiness", json={"answers": {**ALL_NO, "heart": True}})
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


def test_the_answers_are_in_the_export(signed_in: TestClient) -> None:
    signed_in.put("/api/readiness", json={"answers": ALL_NO})
    exported = signed_in.get("/api/account/export")  # this client signed in just now
    zipped = zipfile.ZipFile(io.BytesIO(exported.content))
    (row,) = json.loads(zipped.read("data.json"))["tables"]["readiness_answers"]
    assert row["answers"] == ALL_NO
