"""Logs a connected AI proposed, in Telegram (ADR-0058): "From “Claude”: ..." with Save and
Discard.

Each proposal is sent once: at once after the AI proposes it, and by a check every few minutes
for any whose send failed because Telegram was unreachable. One Telegram refuses outright is
not tried again and doesn't hold up the others; it stays on Today in the app.

Callback data is ``lp:save:<token>`` or ``lp:discard:<token>``; the service looks the token up,
so an old or forged button can't save anything that isn't waiting. A cardio one has a button per
kind instead of Save, ``lp:zone2:<token>`` and ``lp:moderate:<token>``: the person picks which it
was, and the text names the coach's suggestion (ADR-0067, 2026-10-24). How hard it felt is asked
on the web card only, so a cardio one saved here has no effort, like a typed log.
Saving or discarding here or on Today resolves it in both places: a button pressed afterwards
answers "already saved" or that it has gone. Saving one for a day that already has its session
asks first (ADR-0060, ``bot.clash``), with ``lp:<answer>:<token>`` buttons; it keeps waiting
until it is answered.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.bot import clash as clash_ui
from training_coach.bot import links
from training_coach.bot.buttons import edit_quietly
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.queue import local_date
from training_coach.services import proposals
from training_coach.services.day_clash import MOVE, Clash, Refused, Resolution

log = structlog.get_logger(__name__)

PREFIX = "lp"
PATTERN = rf"^{PREFIX}:"
PICKS = {"zone2": "zone2", "moderate": "moderate-cardio"}  # a cardio button: the kind it saves
ACTIONS = frozenset({"save", "discard", *PICKS})
TOKEN_LENGTH = 32
EVERY = timedelta(minutes=5)
JOB = "proposals.announce"
ASK = "Nothing is saved until you tap Save."
ASK_CARDIO = "Nothing is saved until you tap Zone 2 or Moderate."
UNPICKED = "Not saved yet: tap Zone 2 or Moderate."
DISCARDED = "Discarded. Nothing was saved."
GONE = "That proposal has gone: it expired after 24 hours, or its app was disconnected."
ALREADY = {
    proposals.SAVED: "Already saved.",
    proposals.DISCARDED: "Already discarded. Nothing was saved.",
}
FAILED = "Couldn't save that just now. Try again, or use Today in the app."
WAITING = "Not saved: it's still waiting for Save or Discard."

# Like bot.app.send_outcome: SENT, UNREACHABLE (try again later) or REFUSED (never again).
Send = Callable[..., Awaitable[str]]
SENT, UNREACHABLE, REFUSED = "sent", "unreachable", "refused"


@dataclass(frozen=True)
class Press:
    action: str
    token: str


def parse(data: str | None) -> Press | None:
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != PREFIX:
        return None
    if parts[1] not in ACTIONS and not clash_ui.is_answer(parts[1]):
        return None
    token = parts[2]
    if len(token) != TOKEN_LENGTH or any(c not in "0123456789abcdef" for c in token):
        return None
    return Press(parts[1], token)


def markup(token: str, *, cardio: bool = False) -> InlineKeyboardMarkup:
    """Save and Discard; for cardio, Zone 2, Moderate and Discard: the person picks."""
    saves = (
        [
            InlineKeyboardButton("Zone 2", callback_data=f"{PREFIX}:zone2:{token}"),
            InlineKeyboardButton("Moderate", callback_data=f"{PREFIX}:moderate:{token}"),
        ]
        if cardio
        else [InlineKeyboardButton("Save", callback_data=f"{PREFIX}:save:{token}")]
    )
    discard = InlineKeyboardButton("Discard", callback_data=f"{PREFIX}:discard:{token}")
    return InlineKeyboardMarkup([[*saves, discard]])


def text(found: proposals.Pending) -> str:
    """Plain text (no parse mode), so the app's claimed name can't format anything."""
    return f"{found.text}\n\n{ASK_CARDIO if found.kind == proposals.CARDIO else ASK}"


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
        # Token -> the clash shown for it, and a day to move to found taken (ADR-0060).
        self.asked: dict[str, tuple[Clash, date | None]] = {}
        # Token -> the kind of cardio picked, kept while its clash question is answered; only
        # for a token that matched a waiting proposal. Lost on a restart: then it is asked again.
        self.picked: dict[str, str] = {}

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
                buttons = markup(one.token, cardio=one.kind == proposals.CARDIO)
                sent = await self.send(bot, owner, text(one), reply_markup=buttons)
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
        """Save, a kind of cardio, or Discard. Strangers get nothing, not even an answer (T1)."""
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
        asked = self.asked.get(press.token)
        pick = PICKS.get(press.action)
        if press.action == "cancel" or (press.action == MOVE and asked is not None):
            await edit_quietly(query.edit_message_reply_markup(None))
            if press.action == "cancel":
                self.asked.pop(press.token, None)
                await query.message.reply_text(WAITING, reply_markup=self._waiting(press.token))
            else:
                assert asked is not None  # noqa: S101 - checked above
                today = local_date(now, self.settings.tz)
                days = clash_ui.days_keyboard(PREFIX, press.token, asked[0], today, asked[1])
                await query.message.reply_text(clash_ui.MOVE_ASK_BUTTONS, reply_markup=days)
            return
        answer = None
        if press.action not in ACTIONS:  # an answer to the question
            if asked is None:  # never asked, or forgotten in a restart
                await query.message.reply_text(WAITING, reply_markup=self._waiting(press.token))
                return
            answer = clash_ui.resolution(press.action, asked[0], local_date(now, self.settings.tz))
        result: proposals.Resolved | Clash | Refused
        try:
            with session_scope(self.sessions) as session:
                if press.action == "discard":
                    result = proposals.discard(session, press.token, now, "telegram")
                    reply = DISCARDED if isinstance(result, proposals.Discarded) else ""
                else:
                    result = proposals.save(
                        session,
                        press.token,
                        self.settings.tz,
                        now,
                        "telegram",
                        answer,
                        cardio=pick or self.picked.get(press.token),
                    )
                    reply = ""
                    if isinstance(result, proposals.Unpicked):
                        reply, reply_markup = UNPICKED, markup(press.token, cardio=True)
                    elif isinstance(result, Clash | Refused):
                        reply, reply_markup = self._ask(press.token, result, answer, now)
                    elif isinstance(result, proposals.Saved):
                        reply = saved_text(result)
                        reply_markup = links.with_open(None, self.settings.public_url, links.HOME)
                    elif isinstance(result, proposals.Changed):
                        reply = f"Not saved: {result.reason}. Ask your AI again if you want it."
        except SQLAlchemyError as exc:  # keep the buttons, so it can be pressed again
            log.error("bot.proposal_failed", error=type(exc).__name__)
            await query.message.reply_text(FAILED)
            return
        if not isinstance(result, Clash | Refused):
            self.asked.pop(press.token, None)
            self.picked.pop(press.token, None)
        elif pick is not None:  # it is waiting, for the answer to the question
            self.picked[press.token] = pick
        if isinstance(result, proposals.Already):
            reply = ALREADY[result.status]
        elif isinstance(result, proposals.Gone):
            reply = GONE
        await edit_quietly(query.edit_message_reply_markup(None))
        await query.message.reply_text(reply, reply_markup=reply_markup)
        log.info("bot.proposal_answered", action=press.action, outcome=type(result).__name__)

    def _waiting(self, token: str) -> InlineKeyboardMarkup:
        """The buttons of one still waiting: a button per kind for cardio, looked up rather than
        remembered, so they come back after a restart."""
        try:
            with session_scope(self.sessions) as session:
                kind = proposals.waiting_kind(session, token, datetime.now(UTC))
        except SQLAlchemyError as exc:
            log.error("bot.proposal_failed", error=type(exc).__name__)
            kind = None
        return markup(token, cardio=kind == proposals.CARDIO or token in self.picked)

    def _ask(
        self, token: str, result: Clash | Refused, answer: Resolution | None, now: datetime
    ) -> tuple[str, InlineKeyboardMarkup]:
        """The question (again), or the days to move to when the one picked was taken."""
        shown = self.asked.get(token)
        if shown is not None and (isinstance(result, Refused) or result.moving):
            taken = result.day if isinstance(result, Clash) else shown[1]
            self.asked[token] = (shown[0], taken)
            today = local_date(now, self.settings.tz)
            days = clash_ui.days_keyboard(PREFIX, token, shown[0], today, taken)
            why = clash_ui.taken_text(result) if isinstance(result, Clash) else result.reason
            return f"{why}\n\n{clash_ui.MOVE_ASK_BUTTONS}", days
        assert isinstance(result, Clash)  # noqa: S101 - a refusal only answers a move
        self.asked[token] = (result, None)
        reply = clash_ui.text(result)
        if answer is not None:
            reply = f"{clash_ui.CHANGED}\n\n{reply}"
        return reply, clash_ui.keyboard(PREFIX, token, len(result.recorded) == 1)
