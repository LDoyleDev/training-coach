import pytest
import respx
from pydantic import SecretStr
from telegram import Bot, Update
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
        assert 42 in handler.filters.user_ids  # type: ignore[union-attr]  # BaseFilter has no user_ids; this one is filters.User


TELEGRAM = r"https://api\.telegram\.org/bot[^/]+/"
BOT_USER = {"id": 1, "is_bot": True, "first_name": "Coach", "username": "coach_bot"}
OWNER, STRANGER = 42, 99


def _help_from(user_id: int, bot: Bot) -> Update:
    return Update.de_json(
        {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1_790_000_000,
                "chat": {"id": user_id, "type": "private"},
                "from": {"id": user_id, "is_bot": False, "first_name": "Someone"},
                "text": "/help",
                "entities": [{"type": "bot_command", "offset": 0, "length": 5}],
            },
        },
        bot,
    )


@pytest.mark.parametrize(("sender", "replies"), [(OWNER, 1), (STRANGER, 0)])
async def test_only_the_owner_gets_a_reply(sender: int, replies: int) -> None:
    """Threat model T1: a real update from a stranger reaches no handler and sends nothing."""
    application = build_bot(
        Settings(
            environment="test",
            telegram_bot_token=SecretStr("123456:TEST-TOKEN"),
            telegram_allowed_user_id=OWNER,
        )
    )
    with respx.mock(assert_all_called=False) as telegram:
        telegram.post(url__regex=TELEGRAM + "getMe$").respond(json={"ok": True, "result": BOT_USER})
        send = telegram.post(url__regex=TELEGRAM + "sendMessage$").respond(
            json={
                "ok": True,
                "result": {
                    "message_id": 2,
                    "date": 1_790_000_000,
                    "chat": {"id": sender, "type": "private"},
                    "text": "ok",
                },
            }
        )
        await application.initialize()
        try:
            await application.process_update(_help_from(sender, application.bot))
        finally:
            await application.shutdown()
    assert send.call_count == replies
