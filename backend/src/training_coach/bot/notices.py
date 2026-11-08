"""What a release changed in the plan (ADR-0087), told on Telegram once. A check every few minutes
sends each person any of theirs not yet told, as one message in their own chat; one Telegram
can't reach waits for the next check, and one it refuses isn't tried again, as it still shows in
the app."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.exc import SQLAlchemyError
from telegram import Bot
from telegram.ext import ContextTypes

from training_coach.bot.gate import People, Person
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
    def __init__(self, settings: Settings, people: People, send: Send) -> None:
        self.settings = settings
        self.people = people  # whom they are told to: each with their own sessions
        self.send = send

    async def job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.tell(context.bot)

    async def tell(self, bot: Bot) -> None:
        for me in self.people():
            await self._tell(bot, me)

    async def _tell(self, bot: Bot, me: Person) -> None:
        try:
            with session_scope(me.sessions) as session:
                found = [(n.id, n.text) for n in plan_notices.untold(session)]
        except SQLAlchemyError as exc:
            log.error("bot.notices_failed", error=type(exc).__name__)
            return
        if not found:
            return
        sent = await self.send(bot, me.chat, message([text for _, text in found]))
        if sent == UNREACHABLE:
            log.warning("bot.notices_not_sent")
            return
        try:
            with session_scope(me.sessions) as session:
                plan_notices.mark_told(session, [i for i, _ in found], datetime.now(UTC))
        except SQLAlchemyError as exc:
            log.error("bot.notices_failed", error=type(exc).__name__)
