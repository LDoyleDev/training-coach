"""An admin's recovery link for a member (ADR-0059, I1): once, for 24 hours, only the newest; it
recovers like /recover; an admin's own browser can't open it; the member is told when it is made
and when it is used, and Account shows the recovery for 30 days."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select

from tests.alerts import capture
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Passkey, User, WebSession
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.services import auth, users
from training_coach.services.seed import apply_seed, load_plan

BASE = "https://testserver"
MEMBER = 2


@pytest.fixture
def settings(engine: Engine) -> Settings:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
        shared.add(User(id=MEMBER, role=users.MEMBER, label="Mum"))
        shared.flush()
        apply_seed(shared, load_plan())
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as theirs:
        theirs.add(Passkey(credential_id="lost", public_key=b"k", sign_count=0, name="Old phone"))
    return Settings(environment="test", database_url=str(engine.url), multi_user=True)


def _client(settings: Settings, engine: Engine, user: int | None) -> TestClient:
    client = TestClient(create_app(settings), base_url=BASE)
    client.__enter__()
    if user is not None:
        with make_session_factory(engine, user_id=user)() as bound:
            token = auth.create_link(bound, datetime.now(UTC), auth.RECOVER)
            bound.commit()
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
    return client


@pytest.fixture
def admin(settings: Settings, engine: Engine) -> Iterator[TestClient]:
    client = _client(settings, engine, users.OWNER)
    yield client
    client.__exit__(None, None, None)


@pytest.fixture
def phone(settings: Settings, engine: Engine) -> Iterator[TestClient]:
    """The member's new phone: signed in nowhere."""
    client = _client(settings, engine, None)
    yield client
    client.__exit__(None, None, None)


def _link(admin: TestClient) -> str:
    made = admin.post(f"/api/people/{MEMBER}/recovery")
    assert made.status_code == 200, made.text
    token: str = made.json()["token"]
    return token


def _passkeys(engine: Engine) -> int:
    with session_scope(make_session_factory(engine)) as shared:
        query = select(func.count()).select_from(Passkey).where(Passkey.user_id == MEMBER)
        return shared.scalar(query, execution_options={ALL_USERS: True}) or 0


def test_the_member_recovers_on_their_own_phone_and_is_told_each_time(
    admin: TestClient, phone: TestClient, engine: Engine
) -> None:
    told = capture(admin, MEMBER, chat=7777)
    token = _link(admin)
    assert told == [
        "The admin made a recovery link for you on Training Coach. Use it only if you asked "
        "for one; if you didn't, tell them."
    ]
    phone.app.state.send = admin.app.state.send  # type: ignore[attr-defined]  # a FastAPI app
    assert phone.post("/api/auth/redeem", json={"token": token}).status_code == 204
    assert phone.get("/api/auth/me").json()["user_id"] == MEMBER
    assert _passkeys(engine) == 0  # as /recover: whoever had the old phone is cut off
    assert "recovered with the admin's link" in told[-1]
    assert phone.get("/api/auth/me").json()["recovered_by_admin_at"] is not None


def test_account_shows_it_for_30_days_then_not(
    admin: TestClient, phone: TestClient, engine: Engine
) -> None:
    assert phone.post("/api/auth/redeem", json={"token": _link(admin)}).status_code == 204
    with time_machine.travel(datetime.now(UTC) + timedelta(days=29)):
        assert phone.get("/api/auth/me").json()["recovered_by_admin_at"] is not None
    with time_machine.travel(datetime.now(UTC) + timedelta(days=31)):
        assert phone.get("/api/auth/me").json()["recovered_by_admin_at"] is None


def test_an_admins_browser_cant_open_it_and_it_stays_usable(
    admin: TestClient, phone: TestClient
) -> None:
    token = _link(admin)
    assert admin.post("/api/auth/redeem", json={"token": token}).status_code == 403
    assert admin.get("/api/auth/me").json()["user_id"] == users.OWNER  # still the admin
    assert phone.post("/api/auth/redeem", json={"token": token}).status_code == 204


def test_only_the_newest_link_works(admin: TestClient, phone: TestClient) -> None:
    first, second = _link(admin), _link(admin)
    assert phone.post("/api/auth/redeem", json={"token": first}).status_code == 401
    assert phone.post("/api/auth/redeem", json={"token": second}).status_code == 204


def test_it_works_once_and_for_24_hours(admin: TestClient, phone: TestClient) -> None:
    late = _link(admin)
    with time_machine.travel(datetime.now(UTC) + timedelta(hours=25)):
        assert phone.post("/api/auth/redeem", json={"token": late}).status_code == 401
    once = _link(admin)
    assert phone.post("/api/auth/redeem", json={"token": once}).status_code == 204
    assert phone.post("/api/auth/redeem", json={"token": once}).status_code == 401


def test_other_browsers_of_the_member_are_signed_out(
    settings: Settings, admin: TestClient, phone: TestClient, engine: Engine
) -> None:
    old = _client(settings, engine, MEMBER)
    try:
        assert phone.post("/api/auth/redeem", json={"token": _link(admin)}).status_code == 204
        assert old.get("/api/auth/me").status_code == 401
    finally:
        old.__exit__(None, None, None)
    with session_scope(make_session_factory(engine)) as shared:
        live = (
            select(func.count())
            .select_from(WebSession)
            .where(WebSession.user_id == MEMBER, WebSession.ended_at.is_(None))
        )
        assert shared.scalar(live, execution_options={ALL_USERS: True}) == 1  # the new phone


@pytest.mark.parametrize("who", [users.OWNER, 99])
def test_only_for_a_member(admin: TestClient, who: int) -> None:
    assert admin.post(f"/api/people/{who}/recovery").status_code == 404


def test_a_member_cant_make_one(settings: Settings, engine: Engine) -> None:
    member = _client(settings, engine, MEMBER)
    try:
        assert member.post(f"/api/people/{MEMBER}/recovery").status_code == 403
    finally:
        member.__exit__(None, None, None)


def test_it_needs_a_recent_sign_in(admin: TestClient) -> None:
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        assert admin.post(f"/api/people/{MEMBER}/recovery").status_code == 403


def test_nothing_while_multi_user_is_off(settings: Settings, engine: Engine) -> None:
    owner = _client(settings.model_copy(update={"multi_user": False}), engine, users.OWNER)
    try:
        assert owner.post(f"/api/people/{MEMBER}/recovery").status_code == 404
    finally:
        owner.__exit__(None, None, None)
