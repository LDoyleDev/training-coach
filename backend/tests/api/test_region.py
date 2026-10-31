"""The EU and EEA only (ADR-0085 layer 2): CF-IPCountry, believed only from a trusted proxy."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from training_coach.api.app import create_app
from training_coach.config import Settings

TUNNEL = ("172.17.0.1", 50000)  # the Docker bridge: a trusted proxy by default
STRANGER = ("203.0.113.9", 50000)  # reached the port some other way


def _client(engine: Engine, web: Path, peer: tuple[str, int]) -> TestClient:
    (web / "index.html").write_text("<!doctype html><title>Training Coach</title>")
    settings = Settings(environment="test", database_url=str(engine.url), web_dist_dir=web)
    return TestClient(create_app(settings), base_url="https://testserver", client=peer)


@pytest.fixture
def tunnel(engine: Engine, tmp_path: Path) -> Iterator[TestClient]:
    with _client(engine, tmp_path, TUNNEL) as client:
        yield client


@pytest.mark.parametrize("country", ["US", "GB", "CH", "XX", "T1"])
def test_browser_routes_from_outside_the_list_get_451(tunnel: TestClient, country: str) -> None:
    page = tunnel.get("/signin", headers={"CF-IPCountry": country})
    assert page.status_code == 451
    assert "Not available in your region" in page.text
    assert page.headers["cache-control"] == "no-store"
    assert page.headers["x-content-type-options"] == "nosniff"  # security headers too
    api = tunnel.get("/api/auth/me", headers={"CF-IPCountry": country})
    assert api.status_code == 451
    assert api.json() == {"detail": "Not available in your region"}
    # A change is refused the same way, before any route reads it.
    assert tunnel.post("/api/auth/redeem", headers={"CF-IPCountry": country}).status_code == 451


@pytest.mark.parametrize("country", ["DE", "de", "NO", "IS", "LI", "AX", "RE"])
def test_listed_countries_reach_the_app(tunnel: TestClient, country: str) -> None:
    assert tunnel.get("/signin", headers={"CF-IPCountry": country}).status_code == 200
    assert tunnel.get("/api/auth/me", headers={"CF-IPCountry": country}).status_code == 401


def test_without_the_header_the_app_is_open(tunnel: TestClient) -> None:
    """Local development, tests, a process on the Pi, or a Cloudflare header that never came:
    the owner is never locked out by its absence."""
    assert tunnel.get("/signin").status_code == 200
    assert tunnel.get("/signin", headers={"CF-IPCountry": ""}).status_code == 200


def test_the_header_is_ignored_from_an_untrusted_peer(engine: Engine, tmp_path: Path) -> None:
    """Anyone reaching the port without the tunnel could write any country (LAN, Tailscale);
    they're judged as if they named none, like CF-Connecting-IP."""
    with _client(engine, tmp_path, STRANGER) as client:
        assert client.get("/signin", headers={"CF-IPCountry": "US"}).status_code == 200
        assert client.get("/signin", headers={"CF-IPCountry": "DE"}).status_code == 200


@pytest.mark.parametrize(
    "path",
    [
        "/mcp",
        "/oauth/token",
        "/oauth/register",
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp",
        "/.well-known/oauth-authorization-server",
        "/healthz",
    ],
)
def test_machine_called_paths_are_exempt(tunnel: TestClient, path: str) -> None:
    """An AI app's servers call these from the US (ADR-0054); their own checks guard them."""
    headers = {"CF-IPCountry": "US"}
    assert tunnel.post(path, headers=headers).status_code != 451
    assert tunnel.get(path, headers=headers).status_code != 451


def test_connecting_an_ai_needs_a_visit_from_europe(tunnel: TestClient) -> None:
    """The consent steps a person takes in the browser are not exempt."""
    for path in ("/oauth/authorize", "/connect", "/api/connect/details"):
        assert tunnel.get(path, headers={"CF-IPCountry": "US"}).status_code == 451, path
