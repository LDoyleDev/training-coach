"""The request guard (security review, 2026-10-10): changes only from the app's own pages,
bounded bodies, no caching of personal answers; and the server settings that go with it."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach import __main__ as main
from training_coach.api.app import create_app
from training_coach.api.auth import COOKIE
from training_coach.api.security import MAX_BODY, SECURITY_HEADERS
from training_coach.config import Settings
from training_coach.db.session import make_engine

ORIGIN = "https://coach.example.com"


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as test_client:
        yield test_client


def _signout(client: TestClient, **headers: str) -> int:
    return client.post("/api/auth/signout", headers=headers).status_code


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example"},
        {"Origin": "https://other.vybe-dev.com"},  # a sibling site SameSite would let through
        {"Origin": "null"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Sec-Fetch-Site": "same-site"},
    ],
)
def test_changes_from_other_sites_are_refused(client: TestClient, headers: dict[str, str]) -> None:
    answer = client.post("/api/auth/signout", headers=headers)
    assert answer.status_code == 403
    for header in SECURITY_HEADERS:
        assert header in answer.headers  # a refusal carries the security headers too


@pytest.mark.parametrize(
    "headers",
    [{"Origin": ORIGIN}, {"Sec-Fetch-Site": "same-origin"}, {"Sec-Fetch-Site": "none"}, {}],
)
def test_changes_from_the_app_or_no_browser_page_pass(
    client: TestClient, headers: dict[str, str]
) -> None:
    assert _signout(client, **headers) == 204


def test_reading_is_never_refused_by_origin(client: TestClient) -> None:
    answer = client.get("/api/auth/me", headers={"Origin": "https://evil.example"})
    assert answer.status_code == 401  # not signed in, but not refused as cross-site


def test_large_bodies_are_refused_before_they_are_read(client: TestClient) -> None:
    big = '{"token": "' + "a" * MAX_BODY + '"}'
    answer = client.post(
        "/api/auth/redeem", content=big, headers={"Content-Type": "application/json"}
    )
    assert answer.status_code == 413
    bogus = client.post("/api/auth/redeem", headers={"Content-Length": "lots"})
    assert bogus.status_code == 413


def test_a_streamed_change_must_say_how_long_it_is(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b'{"token": "'
        yield b'a"}'

    answer = client.post("/api/auth/redeem", content=chunks())
    assert answer.status_code == 411


def test_photos_keep_their_own_larger_limit(client: TestClient) -> None:
    upload = client.put(
        "/api/photos/2026-10-10/front",
        content=bytes(MAX_BODY + 1),
        headers={"Content-Type": "image/jpeg"},
    )
    assert upload.status_code == 401  # reached the route: not signed in, not "too large"


def test_api_answers_are_never_cached(client: TestClient) -> None:
    for path in ("/api/auth/me", "/api/plan"):  # all personal: the site is private (ADR-0041)
        assert client.get(path).headers["cache-control"] == "no-store"


def test_the_session_cookie_is_locked_to_this_host() -> None:
    assert COOKIE.startswith("__Host-")


def test_the_server_never_trusts_forwarded_addresses(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}
    monkeypatch.setattr(main.uvicorn, "run", lambda *_a, **kw: seen.update(kw))
    monkeypatch.setattr(main, "create_app", lambda _settings: object())
    main.serve()
    assert seen["proxy_headers"] is False
    assert "forwarded_allow_ips" not in seen


def test_database_errors_never_show_their_values(tmp_path: Any) -> None:
    engine = make_engine(f"sqlite:///{tmp_path / 'x.db'}")
    assert engine.hide_parameters
    engine.dispose()


def test_without_a_public_url_there_is_no_origin_to_check(engine: Engine) -> None:
    """Development without TC_PUBLIC_URL: no sign-in exists, so nothing to protect by origin."""
    settings = Settings(environment="test", database_url=str(engine.url))
    with TestClient(create_app(settings), base_url="http://localhost") as local:
        answer = local.post("/api/auth/signout", headers={"Origin": "http://localhost:5173"})
        assert answer.status_code == 204
