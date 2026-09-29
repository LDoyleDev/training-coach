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
