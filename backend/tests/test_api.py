from pathlib import Path

from fastapi.testclient import TestClient

from training_coach import __version__
from training_coach.api.app import create_app
from training_coach.api.security import SECURITY_HEADERS
from training_coach.config import Settings


def test_healthz_reports_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__, "bot_enabled": False}


def test_security_headers_on_every_response(client: TestClient) -> None:
    response = client.get("/does-not-exist")
    for header, value in SECURITY_HEADERS.items():
        assert response.headers[header] == value


def test_serves_built_dashboard_when_configured(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<h1>dashboard</h1>")
    settings = Settings(environment="test", web_dist_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        assert "dashboard" in client.get("/").text
        assert client.get("/healthz").json()["status"] == "ok"
