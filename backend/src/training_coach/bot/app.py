"""Telegram bot. Long polling only: no inbound port is ever opened (ADR-0009).

Every handler is registered behind ``owner_only`` so the bot ignores anyone who
is not ``TC_TELEGRAM_ALLOWED_USER_ID``.
"""

import structlog
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from training_coach.config import Settings

log = structlog.get_logger(__name__)

HELP_TEXT = (
    "Training Coach\n\n/today - what's left today\n/week - this week's plan\n/help - this message"
)


def owner_only(settings: Settings) -> filters.BaseFilter:
    if settings.telegram_allowed_user_id is None:
        raise ValueError("TC_TELEGRAM_ALLOWED_USER_ID must be set to run the bot")
    return filters.User(user_id=settings.telegram_allowed_user_id)


async def help_command(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message is not None:
        await update.effective_message.reply_text(HELP_TEXT)


def build_bot(settings: Settings) -> Application:  # type: ignore[type-arg]
    if settings.telegram_bot_token is None:
        raise ValueError("TC_TELEGRAM_BOT_TOKEN must be set to run the bot")
    application = (
        Application.builder().token(settings.telegram_bot_token.get_secret_value()).build()
    )
    allowed = owner_only(settings)
    application.add_handler(CommandHandler(["start", "help"], help_command, filters=allowed))
    log.info("bot.built", allowed_user_id=settings.telegram_allowed_user_id)
    return application
