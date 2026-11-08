"""What a release changed in the plan (ADR-0087), told on Telegram once. A check every few minutes
sends any not yet told, as one message; one Telegram can't reach waits for the next check, and one
it refuses isn't tried again, as it still shows in the app."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from telegram import Bot
from telegram.ext import ContextTypes

from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.services import plan_notices

log = structlog.get_logger(__name__)

EVERY = timedelta(minutes=5)
JOB = "notices.tell"
UNREACHABLE = "unreachable"  # as bot.app.send_outcome says it

Send = Callable[..., Awaitable[str]]


def message(texts: list[str]) -> str:
    return "\n".join(["Something changed in your plan:", *(f"- {t}" for t in texts)])


class NoticeHandlers:
    def __init__(self, settings: Settings, sessions: sessionmaker[Session], send: Send) -> None:
        self.settings = settings
        self.sessions = sessions
        self.send = send

    async def job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.tell(context.bot)

    async def tell(self, bot: Bot) -> None:
        try:
            with session_scope(self.sessions) as session:
                found = [(n.id, n.text) for n in plan_notices.untold(session)]
        except SQLAlchemyError as exc:
            log.error("bot.notices_failed", error=type(exc).__name__)
            return
        if not found:
            return
        owner = self.settings.telegram_allowed_user_id
        assert owner is not None  # noqa: S101 - the bot runs only with an allowed account
        sent = await self.send(bot, owner, message([text for _, text in found]))
        if sent == UNREACHABLE:
            log.warning("bot.notices_not_sent")
            return
        try:
            with session_scope(self.sessions) as session:
                plan_notices.mark_told(session, [i for i, _ in found], datetime.now(UTC))
        except SQLAlchemyError as exc:
            log.error("bot.notices_failed", error=type(exc).__name__)
