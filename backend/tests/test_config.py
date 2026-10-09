import re
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from training_coach.config import Settings


def test_bot_disabled_without_token_and_owner() -> None:
    assert not Settings(environment="test").bot_enabled


def test_bot_enabled_with_token_and_owner() -> None:
    settings = Settings(
        environment="test", telegram_bot_token=SecretStr("x"), telegram_allowed_user_id=1
    )
    assert settings.bot_enabled


def test_secrets_are_masked_in_repr() -> None:
    settings = Settings(environment="test", telegram_bot_token=SecretStr("super-secret"))
    assert "super-secret" not in repr(settings)


def test_invalid_timezone_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="test", timezone="Mars/Olympus")


def test_timezone_property() -> None:
    assert Settings(environment="test").tz.key == "Europe/Berlin"


def test_empty_env_values_mean_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """A copied .env.example has blank secrets; they must not crash startup or enable the bot."""
    for name in ("TC_TELEGRAM_BOT_TOKEN", "TC_TELEGRAM_ALLOWED_USER_ID", "TC_GROQ_API_KEY"):
        monkeypatch.setenv(name, "")
    settings = Settings(environment="test", _env_file=None)  # type: ignore[call-arg]  # pydantic-settings init kwarg
    assert settings.telegram_allowed_user_id is None
    assert settings.telegram_bot_token is None
    assert not settings.bot_enabled


def test_the_app_port_is_published_on_loopback_only() -> None:
    """TC_TRUSTED_PROXIES trusts Docker's bridge range because only processes on the Pi (the
    Cloudflare tunnel) can reach a port published on 127.0.0.1. Publishing it wider would let
    a LAN host forge CF-Connecting-IP (review of #123), so the compose file must not."""
    compose = (Path(__file__).resolve().parents[2] / "compose.yaml").read_text(encoding="utf-8")
    # Every quoted port mapping: "8080:8080" or "127.0.0.1:8080:8080".
    published = re.findall(r'"((?:[\d.]+:)?\d+:\d+)"', compose)
    assert published
    assert all(port.startswith("127.0.0.1:") for port in published), published
