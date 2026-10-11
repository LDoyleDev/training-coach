"""Workouts from the band, offered in Telegram (ADR-0055): "Walk, 46 min, 38 in zone 2 - count
it?" with Count it / Not this one.

A job looks for new offers every few minutes and sends each once. Callback data is
``bc:<import id>`` to count it or ``bx:<import id>`` to turn it down; the service re-checks the
import, so an old or forged button can't count anything that isn't offered.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.bot.buttons import edit_quietly, row_id
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.queue import local_date
from training_coach.services import band_cardio, cardio, user_settings, workout_log

log = structlog.get_logger(__name__)

COUNT, SKIP = "bc", "bx"
PATTERN = rf"^({COUNT}|{SKIP}):"
EVERY = timedelta(minutes=10)
JOB = "band.offers"
GONE = "That workout isn't on offer any more."
STALE = "Today's session changed meanwhile. Open Today in the app to count it."
SKIPPED = "Left out."

Send = Callable[..., Awaitable[bool]]


def parse(data: str | None) -> tuple[str, int] | None:
    """What a button asks and the import it names, or None for anything malformed."""
    parts = (data or "").split(":")
    if len(parts) != 2 or parts[0] not in (COUNT, SKIP):
        return None
    found = row_id(parts[1])
    return (parts[0], found) if found is not None else None


def markup(offer: band_cardio.Offer) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Count it", callback_data=f"{COUNT}:{offer.id}"),
                InlineKeyboardButton("Not this one", callback_data=f"{SKIP}:{offer.id}"),
            ]
        ]
    )


def counted_text(week: cardio.Week, planned: bool) -> str:
    done = "Counted, and today's session is done." if planned else "Counted."
    target = f" of {week.zone2_target[0]}-{week.zone2_target[1]}" if week.zone2_target else ""
    return f"{done} Zone 2 this week: {week.zone2}{target} min. /undo takes it back."


class BandHandlers:
    def __init__(self, settings: Settings, sessions: sessionmaker[Session], send: Send) -> None:
        self.settings = settings
        self.sessions = sessions
        self.send = send

    def _today(self) -> date:
        return local_date(datetime.now(UTC), self.settings.tz)

    async def announce(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send each new offer once, unless paused. An offer is marked sent only after Telegram
        took it, so a failed send is tried again on the next run (review of #226)."""
        try:
            with session_scope(self.sessions) as session:
                if user_settings.load(session).paused:
                    return
                found = band_cardio.unannounced(session, self._today())
        except SQLAlchemyError as exc:
            log.error("bot.band_offer_failed", error=type(exc).__name__)
            return
        owner = self.settings.telegram_allowed_user_id
        assert owner is not None  # noqa: S101 - owner_only
        bot: Bot = context.bot
        for offer in found:
            if not await self.send(bot, owner, offer.text, reply_markup=markup(offer)):
                log.warning("bot.band_offer_not_sent")
                return  # Telegram is unreachable; the rest wait for the next run too
            with session_scope(self.sessions) as session:
                band_cardio.announced(session, offer.id, datetime.now(UTC))
            log.info("bot.band_offer_sent")

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """Count it or Not this one. Strangers get nothing, not even an answer (T1)."""
        query = update.callback_query
        user = update.effective_user
        if query is None or user is None or user.id != self.settings.telegram_allowed_user_id:
            return
        pressed = parse(query.data)
        if pressed is None or not isinstance(query.message, Message):
            await query.answer()
            return
        await query.answer()
        await edit_quietly(query.edit_message_reply_markup(None))
        action, import_id = pressed
        today = self._today()
        with session_scope(self.sessions) as session:
            if action == SKIP:
                band_cardio.dismiss(session, import_id)
                reply = SKIPPED
            else:
                result = band_cardio.count(session, import_id, today, self.settings.tz)
                if isinstance(result, band_cardio.Gone):
                    reply = GONE
                elif isinstance(result, workout_log.Stale):
                    reply = STALE
                else:
                    reply = counted_text(cardio.week(session, today), result.planned)
        await query.message.reply_text(reply)
        log.info("bot.band_offer_answered", action=action)
