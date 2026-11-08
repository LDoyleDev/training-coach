"""``training-coach notify TEXT``: how jobs outside the app (a failed deploy or off-site backup)
tell the owner on Telegram. The Bot and the send are stubbed; nothing reaches Telegram."""

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine

from training_coach import __main__ as cli
from training_coach.bot import app as bot_app
from training_coach.config import get_settings
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import users

OWNER = 42


class FakeBot:
    def __init__(self, token: str) -> None:
        self.token = token
        self.shut = False

    async def shutdown(self) -> None:
        self.shut = True


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch, engine: Engine) -> Iterator[list[tuple[int, str]]]:
    calls: list[tuple[int, str]] = []

    async def send(_bot: Any, chat_id: int, text: str, **_kw: Any) -> bool:
        calls.append((chat_id, text))
        return True

    monkeypatch.setattr(bot_app, "send_with_retry", send)
    monkeypatch.setattr("telegram.Bot", FakeBot)
    monkeypatch.setenv("TC_ENVIRONMENT", "test")
    monkeypatch.setenv("TC_TELEGRAM_BOT_TOKEN", "123456:TEST-TOKEN")
    monkeypatch.setenv("TC_TELEGRAM_ALLOWED_USER_ID", str(OWNER))
    monkeypatch.setenv("TC_DATABASE_URL", str(engine.url))
    with session_scope(make_session_factory(engine)) as shared:
        users.link_owner(shared, OWNER)
    get_settings.cache_clear()
    yield calls
    get_settings.cache_clear()


def test_notify_sends_the_text_to_the_owner(sent: list[tuple[int, str]]) -> None:
    cli.main(["notify", "  Deploy failed on the Pi.  "])
    assert sent == [(OWNER, "Deploy failed on the Pi.")]


def test_a_long_text_is_cut_to_one_message(sent: list[tuple[int, str]]) -> None:
    cli.main(["notify", "x" * 5000])
    assert len(sent[0][1]) == cli.NOTIFY_LENGTH


def test_nothing_to_send_fails(sent: list[tuple[int, str]]) -> None:
    with pytest.raises(SystemExit) as stop:
        cli.main(["notify", "   "])
    assert stop.value.code == 1
    assert sent == []


def test_telegram_refusing_fails(
    sent: list[tuple[int, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def refuse(*_a: Any, **_kw: Any) -> bool:
        return False

    monkeypatch.setattr(bot_app, "send_with_retry", refuse)
    with pytest.raises(SystemExit) as stop:
        cli.main(["notify", "Backup failed."])
    assert stop.value.code == 1


def test_without_the_bot_configured_it_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TC_ENVIRONMENT", "test")
    monkeypatch.delenv("TC_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("TC_TELEGRAM_BOT_TOKEN", "")
    get_settings.cache_clear()
    with pytest.raises(SystemExit) as stop:
        cli.main(["notify", "Backup failed."])
    assert stop.value.code == 1
    get_settings.cache_clear()


def test_a_network_failure_is_a_failed_alert_not_a_crash(
    sent: list[tuple[int, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    from telegram.error import NetworkError

    async def broken(*_a: Any, **_kw: Any) -> bool:
        raise NetworkError("down")

    monkeypatch.setattr(bot_app, "send_with_retry", broken)
    with pytest.raises(SystemExit) as stop:
        cli.main(["notify", "Backup failed."])
    assert stop.value.code == 1


def test_it_goes_to_the_owners_linked_chat_not_the_configured_one(
    sent: list[tuple[int, str]], engine: Engine
) -> None:
    """After a clash the configured account can be a member's (ADR-0059): the owner's own
    alerts follow the owner's link in the database."""
    with session_scope(make_session_factory(engine)) as shared:
        shared.get_one(User, users.OWNER).telegram_user_id = 77
    cli.main(["notify", "Backup failed."])
    assert sent == [(77, "Backup failed.")]


def test_with_no_link_for_the_owner_nothing_goes_to_anyone(
    sent: list[tuple[int, str]], engine: Engine
) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.get_one(User, users.OWNER).telegram_user_id = None
        shared.flush()
        shared.add(User(id=2, role=users.MEMBER, telegram_user_id=OWNER))
    with pytest.raises(SystemExit) as stop:
        cli.main(["notify", "Backup failed."])
    assert stop.value.code == 1
    assert sent == []


def test_without_a_database_it_falls_back_to_the_configured_account(
    sent: list[tuple[int, str]], monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    missing = tmp_path / "gone.db"
    monkeypatch.setenv("TC_DATABASE_URL", f"sqlite:///{missing.as_posix()}")
    get_settings.cache_clear()
    cli.main(["notify", "The Pi's disk failed."])
    assert sent == [(OWNER, "The Pi's disk failed.")]
    assert not missing.exists()  # it never makes one to ask
