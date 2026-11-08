"""With TC_MULTI_USER off the app is closed to members (ADR-0059, the spec's K): a member in the
database can't use the web app beyond who they are, their export and leaving; their AI app and
their phone are refused too. Their sessions are refused, not ended, so switching back on lets
them straight in. The owner is never closed out."""

from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests import oauth_flow as flow
from tests.api.test_mcp import rpc
from tests.routes import api_routes
from training_coach.api.app import create_app
from training_coach.api.auth import WIND_DOWN
from training_coach.config import Settings
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, ingest_keys, users
from training_coach.services.seed import apply_seed, load_plan

MEMBER = 2
INGEST = "/api/ingest/health-connect"


@pytest.fixture
def two(engine: Engine) -> Engine:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
        shared.add(User(id=MEMBER, role=users.MEMBER))
        shared.flush()
        apply_seed(shared, load_plan())
    return engine


def _app(engine: Engine, multi_user: bool) -> TestClient:
    settings = Settings(
        environment="test",
        database_url=str(engine.url),
        public_url=flow.ORIGIN,
        multi_user=multi_user,
    )
    return TestClient(create_app(settings), base_url=flow.ORIGIN, client=("172.17.0.1", 50000))


def _cookie(engine: Engine, user: int) -> str:
    with make_session_factory(engine, user_id=user)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    return token


@pytest.fixture
def off(two: Engine) -> Iterator[TestClient]:
    with _app(two, multi_user=False) as client:
        yield client


def _sign_in(client: TestClient, engine: Engine, user: int) -> None:
    assert client.post("/api/auth/redeem", json={"token": _cookie(engine, user)}).status_code == 204


@pytest.mark.parametrize("path", ["/api/home", "/api/progress", "/api/plan", "/api/settings"])
def test_a_member_is_refused_everything_while_off(off: TestClient, two: Engine, path: str) -> None:
    _sign_in(off, two, MEMBER)
    assert off.get(path).status_code == 403


def test_a_member_still_has_who_they_are_and_their_export(off: TestClient, two: Engine) -> None:
    """The export-only Account (ADR-0059): who they are, the export, and leaving."""
    _sign_in(off, two, MEMBER)
    assert off.get("/api/auth/me").json()["user_id"] == MEMBER
    assert off.get("/api/account/export").status_code == 200  # just signed in: fresh


def test_every_wind_down_path_is_a_real_route(two: Engine) -> None:
    """Review of #601: a typo or a later rename mustn't silently close the way out."""
    app = create_app(Settings(environment="test", database_url=str(two.url)))
    assert WIND_DOWN - {path for path, _ in api_routes(app)} == set()


def test_who_they_are_says_it_is_closed_and_when_their_data_goes(
    off: TestClient, two: Engine
) -> None:
    """For the closing page: a notice on their next sign-in (ADR-0059)."""
    _sign_in(off, two, MEMBER)
    assert off.get("/api/auth/me").json()["closed"] is True
    assert off.get("/api/auth/me").json()["closing_on"] is None  # until the night's wind-down
    with session_scope(make_session_factory(two)) as shared:
        shared.get_one(User, MEMBER).closing_on = date(2026, 12, 7)
    assert off.get("/api/auth/me").json()["closing_on"] == "2026-12-07"


def test_open_again_it_isnt_closed(two: Engine) -> None:
    with _app(two, multi_user=True) as open_:
        _sign_in(open_, two, MEMBER)
        assert open_.get("/api/auth/me").json()["closed"] is False


def test_a_member_can_still_leave_while_off(off: TestClient, two: Engine) -> None:
    _sign_in(off, two, MEMBER)
    assert off.post("/api/account/leave", json={"confirm": "leave"}).status_code == 204
    with session_scope(make_session_factory(two)) as shared:
        assert shared.get(User, MEMBER) is None


def test_the_owner_is_never_closed_out(off: TestClient, two: Engine) -> None:
    _sign_in(off, two, users.OWNER)
    assert off.get("/api/home").status_code == 200


def test_the_owner_isnt_closed_out_by_their_own_row(off: TestClient, two: Engine) -> None:
    """Decided by id, not role: a wrong role on the owner's row can't lock them out."""
    with session_scope(make_session_factory(two)) as shared:
        shared.get_one(User, users.OWNER).role = users.MEMBER
    _sign_in(off, two, users.OWNER)
    assert off.get("/api/home").status_code == 200


def test_switching_back_on_lets_the_same_session_in(two: Engine) -> None:
    token = _cookie(two, MEMBER)
    with _app(two, multi_user=False) as closed:
        assert closed.post("/api/auth/redeem", json={"token": token}).status_code == 204
        assert closed.get("/api/home").status_code == 403
        cookies = closed.cookies
    with _app(two, multi_user=True) as open_:
        open_.cookies = cookies
        assert open_.get("/api/home").status_code == 200


def test_a_members_ai_app_is_refused_while_off(off: TestClient, two: Engine) -> None:
    theirs = flow.mint(two, flow.ALL, user=MEMBER)
    mine = flow.mint(two, flow.ALL)
    assert rpc(off, theirs, "tools/list").status_code == 403
    assert rpc(off, mine, "tools/list").status_code == 200


def test_a_members_phone_is_refused_and_never_locks_the_owners_out(
    off: TestClient, two: Engine
) -> None:
    """Refused as closed, not as a wrong secret: on the owner's Wi-Fi, ten of them mustn't lock
    the owner's uploads from the same address (review of the joining plan)."""
    secrets = {}
    for person in (users.OWNER, MEMBER):
        with session_scope(make_session_factory(two, user_id=person)) as bound:
            secrets[person] = ingest_keys.make(bound, datetime.now(UTC))
    member = {"Authorization": f"Bearer {secrets[MEMBER]}"}
    for _ in range(12):
        assert off.post(INGEST, json={}, headers=member).status_code == 403
    owner = {"Authorization": f"Bearer {secrets[users.OWNER]}"}
    assert off.post(INGEST, json={}, headers=owner).status_code not in (401, 403, 429)
