"""/share (ADR-0050): the last 4 weeks as a picture, to forward to anyone. No link, nothing
public: the image is all that leaves, and it holds no body data, readiness answers or photos."""

import asyncio
from datetime import UTC, datetime

import structlog
from telegram import Update
from telegram.ext import ContextTypes

from training_coach.bot.gate import Person
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.queue import local_date
from training_coach.services import share_card

log = structlog.get_logger(__name__)

CAPTION = (
    "Your last 4 weeks. Forward it to share it: it holds sessions, cardio minutes and ladder "
    "steps, never body data or photos."
)


class ShareHandlers:
    """Each handler gets the person the gate found and works in their sessions only."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def command(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person
    ) -> None:
        if update.effective_message is None:
            return
        today = local_date(datetime.now(UTC), self.settings.tz)
        with session_scope(me.sessions) as session:
            card = share_card.facts(session, today)
        # Drawing is CPU work: off the event loop the API and bot share.
        image = await asyncio.to_thread(share_card.render, card)
        await update.effective_message.reply_photo(image, caption=CAPTION)
        log.info("bot.share_sent", bytes=len(image))
