"""Sign-in routes (ADR-0036): the cookie, /me, sign-out, and every route's declared access."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.routes import api_routes
from training_coach.api.app import create_app
from training_coach.api.auth import COOKIE, HEALTH_GATES, Admin, admin, owner
from training_coach.api.mcp import connection
from training_coach.api.region import exempt
from training_coach.config import Settings
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth
from training_coach.services.users import OWNER

PUBLIC = {
    "/healthz",
    "/api/auth/redeem",
    "/api/join",  # the invite's token proves it (ADR-0059), and it is off by default
    "/api/auth/signout",
    "/api/auth/passkeys/sign-in/options",
    "/api/auth/passkeys/sign-in",
    "/api/ingest/health-connect",  # the ingest secret, not a cookie (ADR-0055)
    # Connect my AI (ADR-0047 C): what an AI app calls before anyone has approved it, and the
    # consent page's handle-gated reads (mcp-threat-model.md requirement 1).
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-protected-resource/mcp",
    "/.well-known/oauth-authorization-server",
    "/oauth/register",
    "/oauth/authorize",
    "/oauth/token",
    "/api/connect/details",
    "/api/connect/deny",
}
# Called by machines from anywhere, so not held to the EU and EEA (ADR-0085): every other
# route answers 451 to a visitor from elsewhere before its own access check runs.
ANY_REGION = {
    "/healthz",
    "/mcp",
    "/oauth/register",
    "/oauth/token",
    "/.well-known/oauth-protected-resource",
    "/.well-known/oauth-protected-resource/mcp",
    "/.well-known/oauth-authorization-server",
    "/api/ingest/health-connect",  # the band reader keeps sending abroad (1 Nov 2026)
}


@pytest.fixture
def app_client(engine: Engine) -> Iterator[TestClient]:
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        yield client


def _link(engine: Engine, user_id: int = OWNER) -> str:
    with make_session_factory(engine, user_id=user_id)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    return token


def test_a_link_signs_the_browser_in(app_client: TestClient, engine: Engine) -> None:
    assert app_client.get("/api/auth/me").status_code == 401
    response = app_client.post("/api/auth/redeem", json={"token": _link(engine)})
    assert response.status_code == 204
    cookie = response.headers["set-cookie"].lower()
    for flag in ("httponly", "secure", "samesite=strict", "path=/"):
        assert flag in cookie
    me = app_client.get("/api/auth/me").json()
    assert (me["role"], me["closed"], me["closing_on"]) == ("admin", False, None)


def test_a_used_or_made_up_link_is_refused(app_client: TestClient, engine: Engine) -> None:
    token = _link(engine)
    assert app_client.post("/api/auth/redeem", json={"token": token}).status_code == 204
    app_client.cookies.clear()
    assert app_client.post("/api/auth/redeem", json={"token": token}).status_code == 401
    assert app_client.post("/api/auth/redeem", json={"token": "x" * 43}).status_code == 401
    assert app_client.post("/api/auth/redeem", json={"token": "short"}).status_code == 422
    assert app_client.get("/api/auth/me").status_code == 401


def test_signing_out_ends_the_session(app_client: TestClient, engine: Engine) -> None:
    app_client.post("/api/auth/redeem", json={"token": _link(engine)})
    kept = app_client.cookies.get(COOKIE)
    assert app_client.post("/api/auth/signout").status_code == 204
    app_client.cookies.set(COOKIE, kept or "")  # even a copied cookie no longer works
    assert app_client.get("/api/auth/me").status_code == 401
    assert app_client.post("/api/auth/signout").status_code == 204  # harmless when signed out


def test_every_route_is_public_or_owner_only(engine: Engine) -> None:
    """A new route must say who may call it (ADR-0036): listed here as public, behind
    ``owner`` (a session cookie), ``admin`` (an admin's session, ADR-0059), or ``connection`` (an
    AI app's bearer token, ADR-0047 C), never two. Pages of the web app (no schema) only serve
    the static index. And only the ``ANY_REGION`` routes skip the EU and EEA check (ADR-0085)."""
    app = create_app(Settings(environment="test", database_url=str(engine.url)))
    routes = [(path, route) for path, route in api_routes(app) if route.include_in_schema]
    assert len(routes) > 50  # the routers' routes, not just the app's own
    for path, route in routes:
        calls = {dep.call for dep in route.dependant.dependencies}
        # A health gate is owner-kind (ADR-0090): the signed-in person, with consent if a member.
        kinds = [kind for kind in (owner, admin, connection, *HEALTH_GATES) if kind in calls]
        guarded = bool(kinds)
        assert path in PUBLIC or guarded, f"{path} declares no access"
        assert not (path in PUBLIC and guarded), f"{path} is listed as public"
        assert len(kinds) <= 1, f"{path} takes more than one"
        assert (connection in calls) == (path == "/mcp"), path
        assert exempt(path) == (path in ANY_REGION), f"{path}: region exemption changed"


def test_only_an_admin_gets_past_admin(engine: Engine) -> None:
    """Signed in as the owner, the one admin, it answers; as a member, 403; signed out, 401."""
    app = create_app(Settings(environment="test", database_url=str(engine.url)))

    @app.get("/api/test-admin")
    def probe(user: Admin) -> int:
        return user

    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/api/test-admin").status_code == 401
        client.post("/api/auth/redeem", json={"token": _link(engine)})
        assert client.get("/api/test-admin").json() == OWNER
    with TestClient(app, base_url="https://testserver") as member:
        member.post("/api/auth/redeem", json={"token": _link(engine, user_id=2)})
        assert member.get("/api/auth/me").json()["role"] == "member"
        assert member.get("/api/test-admin").status_code == 403


def test_the_signin_page_serves_the_web_app(engine: Engine, tmp_path: Path) -> None:
    """The bot's link lands on /signin, which the web app's own router shows."""
    (tmp_path / "index.html").write_text("<!doctype html><title>Training Coach</title>")
    settings = Settings(environment="test", database_url=str(engine.url), web_dist_dir=tmp_path)
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        for path in (
            "/signin",
            "/account",
            "/session",
            "/tests",
            "/body",
            "/progress",
            "/plan",
            "/join",
            "/start",
        ):
            page = client.get(path)
            assert page.status_code == 200, path
            assert "<title>Training Coach</title>" in page.text


def test_a_renewed_session_sends_its_cookie_again(app_client: TestClient, engine: Engine) -> None:
    """The browser keeps the cookie as long as the server keeps the session (review of #122)."""
    with time_machine.travel(datetime(2026, 10, 9, 12, tzinfo=UTC), tick=False):
        app_client.post("/api/auth/redeem", json={"token": _link(engine)})
        assert "set-cookie" not in app_client.get("/api/auth/me").headers  # same day
    with time_machine.travel(datetime(2026, 11, 7, 12, tzinfo=UTC), tick=False):  # day 29
        renewed = app_client.get("/api/auth/me")
    assert renewed.status_code == 200
    assert "max-age=2592000" in renewed.headers["set-cookie"].lower()
    with time_machine.travel(datetime(2026, 12, 6, 12, tzinfo=UTC), tick=False):  # day 58
        assert app_client.get("/api/auth/me").status_code == 200
