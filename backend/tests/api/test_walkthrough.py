"""The walk-through over the web (ADR-0092): GET what it asks, POST a preview that saves nothing,
and POST the one Save; the owner gets a try-out, answers need consent and are never logged."""

from collections.abc import Iterator
from datetime import UTC, date, datetime
from typing import Any

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Exercise, LadderStep, User, Workout
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.consent import VERSIONS, Category
from training_coach.services import auth, users
from training_coach.services.seed import apply_seed, bundled_plan

BASE = "https://testserver"
MEMBER = 2
NOW = datetime(2026, 11, 9, 9, tzinfo=UTC)  # a Monday, 10:00 in Berlin
TODAY = "2026-11-09"


@pytest.fixture(autouse=True)
def monday() -> Iterator[None]:
    with time_machine.travel(NOW, tick=True):
        yield


@pytest.fixture
def app(engine: Engine) -> Settings:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=MEMBER, role=users.MEMBER))
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, bundled_plan())
    return Settings(environment="test", database_url=str(engine.url), multi_user=True)


def _signed_in(settings: Settings, engine: Engine, user: int) -> Iterator[TestClient]:
    with TestClient(create_app(settings), base_url=BASE) as client:
        with make_session_factory(engine, user_id=user)() as bound:
            token = auth.create_link(bound, datetime.now(UTC))
            bound.commit()
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


@pytest.fixture
def member(app: Settings, engine: Engine) -> Iterator[TestClient]:
    yield from _signed_in(app, engine, MEMBER)


@pytest.fixture
def owner(app: Settings, engine: Engine) -> Iterator[TestClient]:
    yield from _signed_in(app, engine, users.OWNER)


def _step(engine: Engine, slug: str, name: str) -> int:
    with make_session_factory(engine)() as shared:
        return shared.scalars(
            select(LadderStep.id)
            .join(Exercise)
            .where(Exercise.slug == slug, LadderStep.name == name)
        ).one()


def _body(engine: Engine, **changes: Any) -> dict[str, Any]:
    return {
        "starter": "two-days",
        "steps": {"push-up": _step(engine, "push-up", "Hands on a table")},
        "starts_on": TODAY,
        **changes,
    }


def test_get_says_who_its_for_and_what_it_asks(member: TestClient) -> None:
    view = member.get("/api/walkthrough").json()
    assert view["who"] == "member"
    assert view["consent_open"] is False
    assert view["country"] is None
    assert view["readiness"]["due"] is True
    assert len(view["ladders"]) == 13
    assert view["ladders"][0]["slug"] == "goblet-squat"
    push = next(lad for lad in view["ladders"] if lad["slug"] == "push-up")
    bottom, *_ = push["steps"]
    assert (bottom["position"], bottom["question"]) == (0, None)
    assert push["on"] == bottom["id"]
    standard = next(s for s in push["steps"] if s["name"] == "Standard")
    assert standard["marks"] == ["floor"]
    assert standard["question"].endswith("?")
    curl = next(lad for lad in view["ladders"] if lad["slug"] == "kb-curl")
    assert ["kettlebell:8"] in [s["needs"] for s in curl["steps"]]
    assert [s["days"] for s in view["starters"]] == [2, 3, 4]
    first = view["starters"][0]["sessions"][0]
    assert (first["slug"], first["rest_after"]) == ("two-days-a", 2)
    assert first["items"][0]["name"] == "Squat"


def test_the_owner_gets_a_try_out(owner: TestClient) -> None:
    assert owner.get("/api/walkthrough").json()["who"] == "owner_try_out"


def test_the_preview_trims_names_the_week_and_maps_both_places(
    member: TestClient, engine: Engine
) -> None:
    body = _body(engine, session_minutes=20, session_exercises=4, places="both")
    view = member.post("/api/walkthrough/preview", json=body)
    assert view.status_code == 200, view.text
    found = view.json()
    a = found["sessions"][0]
    assert sum(1 for i in a["home"]["items"] if i["kept"]) <= 4
    assert a["home"]["dropped"]
    assert a["on"] == TODAY
    week = [(d["date"], d["session"]) for d in found["week"]]
    assert week[0] == (TODAY, "two-days-a")
    assert week[3] == ("2026-11-12", "two-days-b")  # A, two rest places, B
    assert [d["session"] for d in found["week"]].count(None) == 5
    assert [c["place"] for c in found["coverage"]] == ["home", "gym"]


def test_the_preview_saves_nothing_and_the_owner_gets_one_too(
    owner: TestClient, member: TestClient, engine: Engine
) -> None:
    before = member.get("/api/walkthrough").json()
    assert owner.post("/api/walkthrough/preview", json=_body(engine)).status_code == 200
    assert member.post("/api/walkthrough/preview", json=_body(engine)).status_code == 200
    assert member.get("/api/walkthrough").json() == before


def test_a_locked_step_is_refused_with_the_reason(member: TestClient, engine: Engine) -> None:
    body = _body(engine, steps={"push-up": _step(engine, "push-up", "Standard")}, avoid=["floor"])
    for path in ("/api/walkthrough/preview", "/api/walkthrough"):
        found = member.post(path, json={**body, "revision": "x"})
        assert found.status_code == (422 if path.endswith("preview") else 409)  # stale first
    revision = member.get("/api/walkthrough").json()["revision"]
    found = member.post("/api/walkthrough", json={**body, "revision": revision})
    assert found.status_code == 422
    assert "is locked" in found.json()["detail"]


def test_save_makes_the_plan_and_the_card_is_done(member: TestClient, engine: Engine) -> None:
    revision = member.get("/api/walkthrough").json()["revision"]
    saved = member.post("/api/walkthrough", json={**_body(engine), "revision": revision})
    assert saved.status_code == 200, saved.text
    assert saved.json()["kept"] is False
    assert saved.json()["moved"] == ["Push-up"]
    view = member.get("/api/walkthrough").json()
    assert view["who"] == "done"
    assert view["revision"] == saved.json()["revision"]
    again = member.post("/api/walkthrough", json={**_body(engine), "revision": revision})
    assert again.status_code == 409  # a tab left open on the old plan


ANSWERS = {
    "age_band": "65-74",
    "often": "one_two",
    "weekdays": [0, 3],
    "placement": {"push-up": [{"step": 1, "answer": "not_sure"}]},
}


def test_answers_need_consent_and_are_never_logged(
    member: TestClient, engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    with make_session_factory(engine)() as shared:
        push = [
            s.id
            for s in shared.scalars(select(Exercise).where(Exercise.slug == "push-up")).one().ladder
        ]
    answers = {**ANSWERS, "placement": {"push-up": [{"step": push[2], "answer": "not_sure"}]}}
    revision = member.get("/api/walkthrough").json()["revision"]
    body = {**_body(engine), "revision": revision, "answers": answers}
    refused = member.post("/api/walkthrough", json=body)
    assert refused.status_code == 403
    assert refused.json()["detail"] == {"consent_needed": "walkthrough"}
    version = {"version": VERSIONS[Category.WALKTHROUGH]}
    assert member.put("/api/consents/walkthrough", json=version).status_code == 200
    saved = member.post("/api/walkthrough", json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["kept"] is True
    logged = capsys.readouterr().out + capsys.readouterr().err
    assert "api.walkthrough_saved" in logged
    for answer in ("65-74", "one_two", "not_sure", "weekdays"):
        assert answer not in logged


@pytest.mark.parametrize(
    "answers",
    [
        {"placement": {f"ladder-{n}": [] for n in range(14)}},
        {"placement": {"push-up": [{"step": 1, "answer": "no"}] * 13}},
        {"weekdays": [0, 1, 2, 3, 4, 5, 6, 0]},
        {"weekdays": [7]},
        {"weekdays": [0, 0]},
        {"age_band": "16"},
    ],
)
def test_the_answers_are_bounded(
    member: TestClient, engine: Engine, answers: dict[str, Any]
) -> None:
    revision = member.get("/api/walkthrough").json()["revision"]
    body = {**_body(engine), "revision": revision, "answers": answers}
    assert member.post("/api/walkthrough", json=body).status_code == 422


def test_the_owner_cant_save(owner: TestClient, engine: Engine) -> None:
    revision = owner.get("/api/walkthrough").json()["revision"]
    found = owner.post("/api/walkthrough", json={**_body(engine), "revision": revision})
    assert found.status_code == 403


def test_after_a_workout_it_is_closed(member: TestClient, engine: Engine) -> None:
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as theirs:
        theirs.add(Workout(local_date=date(2026, 11, 8), status="done"))
    view = member.get("/api/walkthrough").json()
    assert view["who"] == "closed"
    saved = member.post("/api/walkthrough", json={**_body(engine), "revision": view["revision"]})
    assert (saved.status_code, saved.json()["detail"]) == (409, "closed")
