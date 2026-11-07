"""Invites (ADR-0059): only an admin makes them, only while TC_MULTI_USER is on; one makes one
member, once, within 72 hours, unless revoked; at most TC_MAX_MEMBERS people."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Exercise, ExerciseState, PlanState, SessionTemplate, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

BASE = "https://testserver"


@pytest.fixture
def seeded(engine: Engine) -> Engine:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    return engine


def _owner(engine: Engine, multi_user: bool = True, max_members: int = 5) -> TestClient:
    settings = Settings(
        environment="test",
        database_url=str(engine.url),
        multi_user=multi_user,
        max_members=max_members,
    )
    client = TestClient(create_app(settings), base_url=BASE)
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    client.__enter__()
    assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
    return client


@pytest.fixture
def admin(seeded: Engine) -> Iterator[TestClient]:
    client = _owner(seeded)
    yield client
    client.__exit__(None, None, None)


def _stranger(client: TestClient) -> TestClient:
    other = TestClient(client.app, base_url=BASE)
    other.__enter__()
    return other


def _invite(admin: TestClient, label: str | None = "Mum") -> str:
    made = admin.post("/api/invites", json={"label": label})
    assert made.status_code == 201
    token: str = made.json()["token"]
    return token


def test_everything_is_off_while_multi_user_is_off(seeded: Engine) -> None:
    owner = _owner(seeded, multi_user=False)
    try:
        assert owner.get("/api/people").status_code == 404
        assert owner.post("/api/invites", json={}).status_code == 404
        assert owner.delete("/api/invites/1").status_code == 404
        assert owner.post("/api/join", json={"token": "x", "adult": True}).status_code == 404
    finally:
        owner.__exit__(None, None, None)


def test_an_invite_makes_one_member_with_their_own_start(admin: TestClient, seeded: Engine) -> None:
    token = _invite(admin)
    assert [i["label"] for i in admin.get("/api/people").json()["invites"]] == ["Mum"]
    joiner = _stranger(admin)
    try:
        assert joiner.post("/api/join", json={"token": token, "adult": True}).status_code == 204
        me = joiner.get("/api/auth/me").json()["user_id"]
        assert me != OWNER
        assert joiner.post("/api/join", json={"token": token, "adult": True}).status_code == 401
    finally:
        joiner.__exit__(None, None, None)
    people = admin.get("/api/people").json()
    assert people["invites"] == []
    assert [m["label"] for m in people["members"]] == ["Mum"]
    assert set(people["members"][0]) == {"label", "joined"}  # nothing of their data
    with make_session_factory(seeded)() as shared:
        person = shared.get(User, me)
        assert person is not None
        assert (person.role, person.label) == ("member", "Mum")
    with make_session_factory(seeded, user_id=me)() as bound:
        assert bound.scalars(select(SessionTemplate)).first() is not None
        assert bound.scalars(select(PlanState)).one().next_template_id is not None
        count = len(bound.scalars(select(Exercise)).all())
        assert len(bound.scalars(select(ExerciseState)).all()) == count


def test_a_member_cannot_see_people_or_invite(admin: TestClient) -> None:
    joiner = _stranger(admin)
    try:
        joiner.post("/api/join", json={"token": _invite(admin), "adult": True})
        assert joiner.get("/api/people").status_code == 403
        assert joiner.post("/api/invites", json={}).status_code == 403
    finally:
        joiner.__exit__(None, None, None)


def test_only_an_adult_joins_and_a_no_leaves_the_invite_open(admin: TestClient) -> None:
    token = _invite(admin)
    joiner = _stranger(admin)
    try:
        assert joiner.post("/api/join", json={"token": token, "adult": False}).status_code == 422
        assert joiner.get("/api/auth/me").status_code == 401
        assert joiner.post("/api/join", json={"token": token, "adult": True}).status_code == 204
    finally:
        joiner.__exit__(None, None, None)


def test_a_revoked_or_expired_invite_lets_nobody_in(admin: TestClient) -> None:
    revoked = _invite(admin, "Dad")
    invite_id = admin.get("/api/people").json()["invites"][0]["id"]
    assert admin.delete(f"/api/invites/{invite_id}").status_code == 204
    assert admin.delete(f"/api/invites/{invite_id}").status_code == 404  # once
    late = _invite(admin, "Sam")
    joiner = _stranger(admin)
    try:
        assert joiner.post("/api/join", json={"token": revoked, "adult": True}).status_code == 401
        with time_machine.travel(datetime.now(UTC) + timedelta(hours=73), tick=False):
            assert joiner.post("/api/join", json={"token": late, "adult": True}).status_code == 401
        assert (
            joiner.post("/api/join", json={"token": "nonsense", "adult": True}).status_code == 401
        )
    finally:
        joiner.__exit__(None, None, None)


def test_open_invites_count_toward_the_limit(seeded: Engine) -> None:
    owner = _owner(seeded, max_members=1)
    try:
        token = _invite(owner)
        assert owner.post("/api/invites", json={}).status_code == 409  # the open one counts
        joiner = _stranger(owner)
        try:
            assert joiner.post("/api/join", json={"token": token, "adult": True}).status_code == 204
        finally:
            joiner.__exit__(None, None, None)
        assert owner.post("/api/invites", json={}).status_code == 409  # a member now
    finally:
        owner.__exit__(None, None, None)


def test_a_full_house_turns_an_invite_away_and_keeps_it(seeded: Engine) -> None:
    owner = _owner(seeded, max_members=1)
    try:
        token = _invite(owner)
        with session_scope(make_session_factory(seeded)) as shared:
            shared.add(User(role="member"))  # someone already in, past the limit's count
        joiner = _stranger(owner)
        try:
            answer = joiner.post("/api/join", json={"token": token, "adult": True})
            assert answer.status_code == 409
        finally:
            joiner.__exit__(None, None, None)
        assert len(owner.get("/api/people").json()["invites"]) == 1  # still open
    finally:
        owner.__exit__(None, None, None)


def test_joining_is_rate_limited_per_address(admin: TestClient) -> None:
    joiner = _stranger(admin)
    try:
        answers = [
            joiner.post("/api/join", json={"token": f"guess-{n}", "adult": True}).status_code
            for n in range(40)
        ]
    finally:
        joiner.__exit__(None, None, None)
    assert 429 in answers
    assert set(answers) <= {401, 429}
