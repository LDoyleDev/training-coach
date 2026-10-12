"""Logs a connected AI proposed, in Telegram (ADR-0058): "From “Claude”: ..." with Save and
Discard.

Each proposal is sent once: at once after the AI proposes it, and by a check every few minutes
for any whose send failed because Telegram was unreachable. One Telegram refuses outright is
not tried again and doesn't hold up the others; it stays on Today in the app.

Callback data is ``lp:save:<token>`` or ``lp:discard:<token>``; the service looks the token up,
so an old or forged button can't save anything that isn't waiting.
Saving or discarding here or on Today resolves it in both places: a button pressed afterwards
answers "already saved" or that it has gone.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.bot import links
from training_coach.bot.buttons import edit_quietly
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.services import proposals

log = structlog.get_logger(__name__)

PREFIX = "lp"
PATTERN = rf"^{PREFIX}:"
ACTIONS = frozenset({"save", "discard"})
TOKEN_LENGTH = 32
EVERY = timedelta(minutes=5)
JOB = "proposals.announce"
ASK = "Nothing is saved until you tap Save."
DISCARDED = "Discarded. Nothing was saved."
GONE = "That proposal has gone: it expired after 24 hours, or its app was disconnected."
ALREADY = {
    proposals.SAVED: "Already saved.",
    proposals.DISCARDED: "Already discarded. Nothing was saved.",
}
FAILED = "Couldn't save that just now. Try again, or use Today in the app."

# Like bot.app.send_outcome: SENT, UNREACHABLE (try again later) or REFUSED (never again).
Send = Callable[..., Awaitable[str]]
SENT, UNREACHABLE, REFUSED = "sent", "unreachable", "refused"


@dataclass(frozen=True)
class Press:
    action: str
    token: str


def parse(data: str | None) -> Press | None:
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != PREFIX or parts[1] not in ACTIONS:
        return None
    token = parts[2]
    if len(token) != TOKEN_LENGTH or any(c not in "0123456789abcdef" for c in token):
        return None
    return Press(parts[1], token)


def markup(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Save", callback_data=f"{PREFIX}:save:{token}"),
                InlineKeyboardButton("Discard", callback_data=f"{PREFIX}:discard:{token}"),
            ]
        ]
    )


def text(found: proposals.Pending) -> str:
    """Plain text (no parse mode), so the app's claimed name can't format anything."""
    return f"{found.text}\n\n{ASK}"


def saved_text(saved: proposals.Saved) -> str:
    undo = " /undo takes it back." if saved.workout else ""
    return f"Saved: {saved.summary}.{undo}"


class ProposalHandlers:
    def __init__(self, settings: Settings, sessions: sessionmaker[Session], send: Send) -> None:
        self.settings = settings
        self.sessions = sessions
        self.send = send
        # The check and a fresh proposal can both reach for the same one: one sender at a time,
        # so nothing goes twice.
        self.sending = asyncio.Lock()

    async def job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self.announce(context.bot)

    async def announce(self, bot: Bot) -> None:
        """Send each waiting proposal once. One is marked sent only after Telegram took it, so a
        failed send is tried again on the next check."""
        async with self.sending:
            try:
                with session_scope(self.sessions) as session:
                    found = proposals.pending(session, datetime.now(UTC), unannounced=True)
            except SQLAlchemyError as exc:
                log.error("bot.proposal_failed", error=type(exc).__name__)
                return
            owner = self.settings.telegram_allowed_user_id
            assert owner is not None  # noqa: S101 - owner_only
            for one in found:
                sent = await self.send(bot, owner, text(one), reply_markup=markup(one.token))
                if sent == UNREACHABLE:
                    log.warning("bot.proposal_not_sent")
                    return  # Telegram is unreachable; the rest wait for the next check too
                mark = proposals.announced if sent == SENT else proposals.announce_refused
                try:
                    with session_scope(self.sessions) as session:
                        mark(session, one.id, datetime.now(UTC))
                except SQLAlchemyError as exc:
                    # Sent but not marked: this one goes again on the next check, so stop
                    # rather than send the rest unmarked too.
                    log.error("bot.proposal_unmarked", error=type(exc).__name__)
                    return
                # Refused for good (blocked, a bad message): logged, never retried, and the
                # card on Today still shows it; the next one still goes.
                log.info("bot.proposal_sent" if sent == SENT else "bot.proposal_refused")

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """Save or Discard. Strangers get nothing, not even an answer (T1)."""
        query = update.callback_query
        user = update.effective_user
        if query is None or user is None or user.id != self.settings.telegram_allowed_user_id:
            return
        await query.answer()
        press = parse(query.data)
        if press is None or not isinstance(query.message, Message):
            return
        now = datetime.now(UTC)
        reply_markup = None
        result: proposals.Resolved
        try:
            with session_scope(self.sessions) as session:
                if press.action == "discard":
                    result = proposals.discard(session, press.token, now, "telegram")
                    reply = DISCARDED if isinstance(result, proposals.Discarded) else ""
                else:
                    result = proposals.save(session, press.token, self.settings.tz, now, "telegram")
                    reply = ""
                    if isinstance(result, proposals.Saved):
                        reply = saved_text(result)
                        reply_markup = links.with_open(None, self.settings.public_url, links.HOME)
                    elif isinstance(result, proposals.Changed):
                        reply = f"Not saved: {result.reason}. Ask your AI again if you want it."
        except SQLAlchemyError as exc:  # keep the buttons, so it can be pressed again
            log.error("bot.proposal_failed", error=type(exc).__name__)
            await query.message.reply_text(FAILED)
            return
        if isinstance(result, proposals.Already):
            reply = ALREADY[result.status]
        elif isinstance(result, proposals.Gone):
            reply = GONE
        await edit_quietly(query.edit_message_reply_markup(None))
        await query.message.reply_text(reply, reply_markup=reply_markup)
        log.info("bot.proposal_answered", action=press.action, outcome=type(result).__name__)
