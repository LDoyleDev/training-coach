import asyncio
import contextlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from training_coach import __version__
from training_coach.api import app as api_app
from training_coach.api.app import _owner_notifier, _report_death, _start_backups, create_app
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
    settings = Settings(
        environment="test", database_url="sqlite:///:memory:", web_dist_dir=tmp_path
    )
    with TestClient(create_app(settings)) as client:
        assert "dashboard" in client.get("/").text
        assert client.get("/healthz").json()["status"] == "ok"


async def test_backups_start_for_a_database_file_and_stop_cleanly(tmp_path: Path) -> None:
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'app.db'}")
    task = _start_backups(settings, notify=None)
    assert task is not None
    assert task.get_name() == "backup.nightly"
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


def test_no_backups_for_an_in_memory_database(settings: Settings) -> None:
    assert _start_backups(settings, notify=None) is None


async def test_backup_failures_are_sent_to_the_owner_only(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[tuple[object, int, str]] = []

    async def fake_send(bot: object, chat_id: int, text: str) -> bool:
        sent.append((bot, chat_id, text))
        return True

    monkeypatch.setattr(api_app, "send_with_retry", fake_send)
    telegram = object()
    owned = settings.model_copy(update={"telegram_allowed_user_id": 4242})
    notify = _owner_notifier(owned, telegram)  # type: ignore[arg-type]  # a stand-in bot
    assert notify is not None
    await notify("backup failed")
    assert sent == [(telegram, 4242, "backup failed")]
    assert _owner_notifier(settings, telegram) is None  # type: ignore[arg-type]  # no owner
    assert _owner_notifier(owned, None) is None  # no bot


async def test_a_dead_backup_loop_is_reported() -> None:
    async def dies() -> None:
        raise OSError("disk gone")

    task = asyncio.create_task(dies())
    with contextlib.suppress(OSError):
        await task
    with capture_logs() as logs:
        _report_death(task)
    assert logs == [{"event": "backup.loop_died", "error": "OSError", "log_level": "error"}]
