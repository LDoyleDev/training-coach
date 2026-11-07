"""Leaving and removing a member over the web (ADR-0059, ADR-0088): POST /api/account/leave and
POST /api/people/{id}/remove. Either deletes everything of the member's, with no fresh start."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.alerts import capture
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Measurement, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, left_list, users
from training_coach.services.seed import apply_seed, load_plan

BASE = "https://testserver"
MEMBER = 2
LEAVE = {"confirm": "leave"}
REMOVE = {"confirm": "remove"}


@pytest.fixture
def app(engine: Engine) -> Settings:
    """The owner and member 2, each with a plan and a measurement; multi-user on."""
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
        shared.add(User(id=MEMBER, role=users.MEMBER, label="Mum"))
        shared.flush()
        apply_seed(shared, load_plan())
    for person in (users.OWNER, MEMBER):
        with session_scope(make_session_factory(engine, user_id=person)) as theirs:
            theirs.add(Measurement(local_date=date(2026, 11, 2), kind="waist", tenths=800))
    return Settings(environment="test", database_url=str(engine.url), multi_user=True)


def _signed_in(settings: Settings, engine: Engine, user: int) -> TestClient:
    client = TestClient(create_app(settings), base_url=BASE)
    client.__enter__()
    with make_session_factory(engine, user_id=user)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
    return client


@pytest.fixture
def member(app: Settings, engine: Engine) -> Iterator[TestClient]:
    client = _signed_in(app, engine, MEMBER)
    yield client
    client.__exit__(None, None, None)


@pytest.fixture
def admin(app: Settings, engine: Engine) -> Iterator[TestClient]:
    client = _signed_in(app, engine, users.OWNER)
    yield client
    client.__exit__(None, None, None)


def _here(engine: Engine, user: int) -> bool:
    with session_scope(make_session_factory(engine)) as shared:
        return shared.get(User, user) is not None


def _listed(engine: Engine) -> list[int]:
    path = left_list.for_url(str(engine.url))
    assert path is not None
    return [e.user_id for e in left_list.read(path)]


def test_a_member_leaves_with_everything_theirs(member: TestClient, engine: Engine) -> None:
    told = capture(member, MEMBER, chat=7777)
    assert member.post("/api/account/leave", json=LEAVE).status_code == 204
    assert not _here(engine, MEMBER)
    assert _here(engine, users.OWNER)
    assert _listed(engine) == [MEMBER]  # kept gone after a restore
    assert member.get("/api/auth/me").status_code == 401  # signed out, and no account to sign in
    assert told == [
        "You left Training Coach and everything of yours was deleted. Backups age out within "
        "5 weeks."
    ]


def test_the_owner_erases_instead_of_leaving(admin: TestClient, engine: Engine) -> None:
    assert admin.post("/api/account/leave", json=LEAVE).status_code == 403
    assert _here(engine, users.OWNER)
    assert _listed(engine) == []
    assert admin.get("/api/auth/me").json() == {"user_id": users.OWNER, "role": "admin"}


@pytest.mark.parametrize("body", [{}, {"confirm": "yes"}, {"confirm": "LEAVE"}])
def test_leaving_needs_the_word_typed(
    member: TestClient, engine: Engine, body: dict[str, str]
) -> None:
    assert member.post("/api/account/leave", json=body).status_code == 422
    assert _here(engine, MEMBER)


def test_leaving_needs_a_recent_sign_in(member: TestClient, engine: Engine) -> None:
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        assert member.post("/api/account/leave", json=LEAVE).status_code == 403
    assert _here(engine, MEMBER)


def test_leaving_works_with_multi_user_off(app: Settings, engine: Engine) -> None:
    """Leaving is always allowed: it is how a member goes when the app closes to them."""
    client = _signed_in(app.model_copy(update={"multi_user": False}), engine, MEMBER)
    try:
        assert client.post("/api/account/leave", json=LEAVE).status_code == 204
    finally:
        client.__exit__(None, None, None)
    assert not _here(engine, MEMBER)


def test_the_admin_removes_a_member_who_is_told(admin: TestClient, engine: Engine) -> None:
    told = capture(admin, MEMBER, chat=7777)
    members = admin.get("/api/people").json()["members"]
    assert [m["id"] for m in members] == [MEMBER]
    assert admin.post(f"/api/people/{MEMBER}/remove", json=REMOVE).status_code == 204
    assert not _here(engine, MEMBER)
    assert _listed(engine) == [MEMBER]
    assert admin.get("/api/people").json()["members"] == []
    assert told == [
        "The admin removed you from Training Coach, and everything of yours was deleted. "
        "Backups age out within 5 weeks."
    ]


@pytest.mark.parametrize("who", [users.OWNER, 99])
def test_only_a_member_can_be_removed(admin: TestClient, engine: Engine, who: int) -> None:
    assert admin.post(f"/api/people/{who}/remove", json=REMOVE).status_code == 404
    assert _here(engine, users.OWNER)


def test_removing_needs_the_word_and_a_recent_sign_in(admin: TestClient, engine: Engine) -> None:
    assert admin.post(f"/api/people/{MEMBER}/remove", json={"confirm": "yes"}).status_code == 422
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        assert admin.post(f"/api/people/{MEMBER}/remove", json=REMOVE).status_code == 403
    assert _here(engine, MEMBER)


def test_a_member_cant_remove_anyone(member: TestClient, engine: Engine) -> None:
    assert member.post(f"/api/people/{MEMBER}/remove", json=REMOVE).status_code == 403
    assert _here(engine, MEMBER)


def test_nobody_is_removed_while_multi_user_is_off(app: Settings, engine: Engine) -> None:
    client = _signed_in(app.model_copy(update={"multi_user": False}), engine, users.OWNER)
    try:
        assert client.post(f"/api/people/{MEMBER}/remove", json=REMOVE).status_code == 404
    finally:
        client.__exit__(None, None, None)
    assert _here(engine, MEMBER)
