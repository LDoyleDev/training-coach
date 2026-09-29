import pytest
from pydantic import SecretStr
from telegram.ext import CommandHandler

from training_coach.bot.app import build_bot, owner_only
from training_coach.config import Settings


def test_owner_only_requires_configured_user() -> None:
    with pytest.raises(ValueError, match="ALLOWED_USER_ID"):
        owner_only(Settings(environment="test"))


def test_build_bot_requires_token() -> None:
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        build_bot(Settings(environment="test", telegram_allowed_user_id=1))


def test_every_handler_is_restricted_to_owner() -> None:
    settings = Settings(
        environment="test",
        telegram_bot_token=SecretStr("123456:TEST-TOKEN"),
        telegram_allowed_user_id=42,
    )
    bot = build_bot(settings)
    handlers = [h for group in bot.handlers.values() for h in group]
    assert handlers
    for handler in handlers:
        assert isinstance(handler, CommandHandler)
        assert 42 in handler.filters.user_ids  # type: ignore[union-attr]
