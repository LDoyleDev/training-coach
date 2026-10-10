"""``training-coach notify TEXT``: how jobs outside the app (a failed deploy or off-site backup)
tell the owner on Telegram. The Bot and the send are stubbed; nothing reaches Telegram."""

from collections.abc import Iterator
from typing import Any

import pytest

from training_coach import __main__ as cli
from training_coach.bot import app as bot_app
from training_coach.config import get_settings

OWNER = 42


class FakeBot:
    def __init__(self, token: str) -> None:
        self.token = token

    async def __aenter__(self) -> "FakeBot":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[tuple[int, str]]]:
    calls: list[tuple[int, str]] = []

    async def send(_bot: Any, chat_id: int, text: str, **_kw: Any) -> bool:
        calls.append((chat_id, text))
        return True

    monkeypatch.setattr(bot_app, "send_with_retry", send)
    monkeypatch.setattr("telegram.Bot", FakeBot)
    monkeypatch.setenv("TC_ENVIRONMENT", "test")
    monkeypatch.setenv("TC_TELEGRAM_BOT_TOKEN", "123456:TEST-TOKEN")
    monkeypatch.setenv("TC_TELEGRAM_ALLOWED_USER_ID", str(OWNER))
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
