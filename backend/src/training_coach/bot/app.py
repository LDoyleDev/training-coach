"""Telegram bot. Long polling only: no inbound port is ever opened (ADR-0009).

Every handler is registered behind ``owner_only`` so the bot ignores anyone who
is not ``TC_TELEGRAM_ALLOWED_USER_ID``.
"""

import asyncio
from datetime import UTC, datetime, time

import structlog
from sqlalchemy.orm import Session, sessionmaker
from telegram import Bot, Update
from telegram.error import NetworkError
from telegram.ext import Application, CommandHandler, ContextTypes, filters

from training_coach.bot.messages import NO_PLAN, today_text, week_text
from training_coach.config import Settings
from training_coach.db.models import UserSettings
from training_coach.db.session import session_scope
from training_coach.domain.queue import local_date
from training_coach.services.today import today as todays_session
from training_coach.services.today import week as upcoming_week

log = structlog.get_logger(__name__)

HELP_TEXT = (
    "Training Coach\n\n"
    "/today - today's session with targets\n"
    "/week - the next 7 sessions\n"
    "/help - this message\n\n"
    "The session for the day also arrives every morning."
)
DEFAULT_MORNING = time(7, 30)
MORNING_JOB = "morning"


def owner_only(settings: Settings) -> filters.BaseFilter:
    if settings.telegram_allowed_user_id is None:
        raise ValueError("TC_TELEGRAM_ALLOWED_USER_ID must be set to run the bot")
    return filters.User(user_id=settings.telegram_allowed_user_id)


async def send_with_retry(
    bot: Bot, chat_id: int, text: str, *, attempts: int = 3, backoff: float = 2.0
) -> bool:
    """Send a scheduled message, retrying network errors with backoff. False if all fail."""
    for attempt in range(1, attempts + 1):
        try:
            await bot.send_message(chat_id=chat_id, text=text)
        except NetworkError as exc:
            log.warning("bot.send_failed", attempt=attempt, error=type(exc).__name__)
            if attempt < attempts:
                await asyncio.sleep(backoff * 2 ** (attempt - 1))
        else:
            return True
    return False


class Handlers:
    """Thin adapters: read through ``services``, format with ``messages``, reply."""

    def __init__(self, settings: Settings, sessions: sessionmaker[Session]) -> None:
        self.settings = settings
        self.sessions = sessions

    def _today_text(self) -> str:
        with session_scope(self.sessions) as session:
            plan = todays_session(session, local_date(datetime.now(UTC), self.settings.tz))
            return NO_PLAN if plan is None else today_text(plan)

    async def help(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message is not None:
            await update.effective_message.reply_text(HELP_TEXT)

    async def today(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message is not None:
            await update.effective_message.reply_text(self._today_text())

    async def week(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        with session_scope(self.sessions) as session:
            days = upcoming_week(session, local_date(datetime.now(UTC), self.settings.tz))
            text = NO_PLAN if days is None else week_text(days)
        if update.effective_message is not None:
            await update.effective_message.reply_text(text)

    async def morning(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        with session_scope(self.sessions) as session:
            prefs = session.get(UserSettings, 1)
            paused = prefs is not None and prefs.paused
        if paused:
            log.info("bot.morning_skipped", reason="paused")
            return
        assert self.settings.telegram_allowed_user_id is not None  # noqa: S101 - owner_only
        if await send_with_retry(
            context.bot, self.settings.telegram_allowed_user_id, self._today_text()
        ):
            log.info("bot.morning_sent")
        else:
            log.error("bot.morning_failed")


def schedule_morning(application: Application, handlers: Handlers, at: time) -> None:  # type: ignore[type-arg]  # see build_bot
    """(Re)schedule the daily morning message at local wall-clock time ``at``.

    The time carries the user's timezone, so the job follows DST: 07:30 stays 07:30 local.
    """
    job_queue = application.job_queue
    assert job_queue is not None  # noqa: S101 - the job-queue extra is a dependency
    for job in job_queue.get_jobs_by_name(MORNING_JOB):
        job.schedule_removal()
    job_queue.run_daily(
        handlers.morning, time=at.replace(tzinfo=handlers.settings.tz), name=MORNING_JOB
    )
    log.info("bot.morning_scheduled", at=at.isoformat())


# PTB's Application takes six type parameters, all fixed by the default builder; spelling them
# out adds nothing, so the bare generic is deliberate.
def build_bot(settings: Settings, sessions: sessionmaker[Session]) -> Application:  # type: ignore[type-arg]
    if settings.telegram_bot_token is None:
        raise ValueError("TC_TELEGRAM_BOT_TOKEN must be set to run the bot")
    application = (
        Application.builder().token(settings.telegram_bot_token.get_secret_value()).build()
    )
    allowed = owner_only(settings)
    handlers = Handlers(settings, sessions)
    application.add_handler(CommandHandler(["start", "help"], handlers.help, filters=allowed))
    application.add_handler(CommandHandler("today", handlers.today, filters=allowed))
    application.add_handler(CommandHandler("week", handlers.week, filters=allowed))

    with session_scope(sessions) as session:
        prefs = session.get(UserSettings, 1)
        at = prefs.morning_time if prefs is not None else DEFAULT_MORNING
    schedule_morning(application, handlers, at)
    log.info("bot.built", allowed_user_id=settings.telegram_allowed_user_id)
    return application
