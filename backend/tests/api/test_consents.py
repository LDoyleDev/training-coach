"""Consent over the web (ADR-0090): GET, PUT and DELETE /api/consents. A member says yes per
category to the wording shown; withdrawing needs a recent sign-in and erases the category. The
owner isn't asked."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Measurement, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.consent import VERSIONS, Category
from training_coach.services import auth, users

BASE = "https://testserver"
MEMBER = 2


@pytest.fixture
def app(engine: Engine) -> Settings:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=MEMBER, role=users.MEMBER, label="Mum"))
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as theirs:
        theirs.add(Measurement(local_date=date(2026, 11, 2), kind="waist", tenths=800))
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


def _open(view: dict[str, object]) -> dict[str, bool]:
    return {c["category"]: c["open"] for c in view["categories"]}  # type: ignore[attr-defined,index]  # JSON


def _measurements(engine: Engine) -> int:
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as theirs:
        return theirs.scalar(select(func.count()).select_from(Measurement)) or 0


def test_a_member_starts_with_everything_closed(member: TestClient) -> None:
    view = member.get("/api/consents").json()
    assert view["asked"] is True
    assert _open(view) == dict.fromkeys(Category, False)
    assert {c["version"] for c in view["categories"]} == set(VERSIONS.values())


def test_a_yes_opens_only_that_category(member: TestClient) -> None:
    given = member.put("/api/consents/body", json={"version": VERSIONS[Category.BODY]})
    assert given.status_code == 200
    assert _open(given.json()) == {
        "body": True,
        "daily_check": False,
        "band": False,
        "walkthrough": False,
    }


def test_a_yes_to_old_wording_is_refused(member: TestClient) -> None:
    stale = member.put("/api/consents/body", json={"version": VERSIONS[Category.BODY] + 1})
    assert stale.status_code == 409
    assert _open(member.get("/api/consents").json())["body"] is False


def test_an_unknown_category_is_refused(member: TestClient) -> None:
    assert member.put("/api/consents/photos", json={"version": 1}).status_code == 422


def test_withdrawing_erases_the_category(member: TestClient, engine: Engine) -> None:
    member.put("/api/consents/body", json={"version": VERSIONS[Category.BODY]})
    withdrawn = member.delete("/api/consents/body")
    assert withdrawn.status_code == 200
    assert _open(withdrawn.json())["body"] is False
    body = next(c for c in withdrawn.json()["categories"] if c["category"] == "body")
    assert body["answer"] == "withdrawn"
    assert _measurements(engine) == 0


def test_withdrawing_needs_a_recent_sign_in(member: TestClient, engine: Engine) -> None:
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        assert member.delete("/api/consents/body").status_code == 403
    assert _measurements(engine) == 1


def test_the_owner_is_not_asked(owner: TestClient) -> None:
    view = owner.get("/api/consents").json()
    assert view["asked"] is False
    assert all(_open(view).values())
    assert owner.put("/api/consents/body", json={"version": 1}).status_code == 409
    assert owner.delete("/api/consents/body").status_code == 409


def test_nobody_signed_in_gets_nothing(client: TestClient) -> None:
    assert client.get("/api/consents").status_code == 401
