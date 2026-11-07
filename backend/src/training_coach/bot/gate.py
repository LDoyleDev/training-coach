"""The sender gate (ADR-0089): the first thing every update meets.

One handler in group -1 decides who an update is from before any other handler runs. It lets
through only a message or a button press, in a private chat whose id is the sender's, from
someone linked in ``users.telegram_user_id``. Strangers, groups, channels and every other kind of
update stop here without a reply, and so does a member while ``TC_MULTI_USER`` is off (ADR-0059).
Someone away from Europe for 30 days gets one line (ADR-0085), except for /login and /recover.

PTB carries on to the next group when a handler raises anything but ``ApplicationHandlerStop``,
so the gate catches everything and stops: it fails closed. A database error is told only to a
sender it has served before in this process, or to the configured owner account, never to a
stranger.
"""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

from training_coach.bot.messages import SOMETHING_WENT_WRONG
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.services import users

log = structlog.get_logger(__name__)

# The only updates the bot asks Telegram for (start_polling's allowed_updates) and lets in.
ALLOWED_UPDATES = ("message", "callback_query")
AWAY_TEXT = (
    "Training Coach serves the EU and EEA only. Open the website from there to turn me back on."
)
# Still answered when paused: the way back into the website, where a visit from Europe counts.
ANYWHERE = frozenset({"/login", "/recover"})
REMEMBERED = 256  # updates whose person the error handler can still look up


@dataclass(frozen=True)
class Person:
    """Who an update is from, as the gate found them."""

    user_id: int
    chat: int  # their private chat, which is their Telegram user id

    @property
    def owner(self) -> bool:
        return self.user_id == users.OWNER

    @property
    def health(self) -> bool:
        """Whether health data is open to them (members are training-only, ADR-0059)."""
        return users.health_open(self.user_id)


class Gate:
    def __init__(self, settings: Settings, shared: sessionmaker[Session]) -> None:
        self.settings = settings
        self.shared = shared  # unbound: users is a shared table
        self.seen: set[int] = set()  # Telegram ids served since start-up
        self.found: OrderedDict[int, Person] = OrderedDict()  # update id -> person

    def person(self, update: object) -> Person | None:
        """Who the gate let ``update`` through for, if anyone (the error handler's question:
        PTB gives it a fresh context)."""
        return self.found.get(update.update_id) if isinstance(update, Update) else None

    async def check(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            person = await self._admit(update)
        except ApplicationHandlerStop:
            raise
        except Exception as exc:  # failing closed is the point: nothing gets past a crash
            log.error("bot.gate_failed", error=type(exc).__name__)
            raise ApplicationHandlerStop from None
        self.found[update.update_id] = person
        while len(self.found) > REMEMBERED:
            self.found.popitem(last=False)

    async def _admit(self, update: Update) -> Person:
        sender, chat = update.effective_user, update.effective_chat
        if (
            (update.message is None and update.callback_query is None)
            or sender is None
            or chat is None
            or chat.type != chat.PRIVATE
            or chat.id != sender.id
        ):
            raise ApplicationHandlerStop
        now = datetime.now(UTC)
        try:
            with session_scope(self.shared) as session:
                user_id = users.by_telegram(session, sender.id)
                served = user_id is not None and users.served_remotely(session, user_id, now)
        except SQLAlchemyError as exc:
            log.error("bot.gate_lookup_failed", error=type(exc).__name__)
            if sender.id in self.seen or sender.id == self.settings.telegram_allowed_user_id:
                await self._reply(update, SOMETHING_WENT_WRONG)
            raise ApplicationHandlerStop from None
        if user_id is None or users.closed_to(user_id, self.settings.multi_user):
            raise ApplicationHandlerStop  # a stranger, or a member while the switch is off
        self.seen.add(sender.id)
        if not served and not _anywhere(update):
            await self._reply(update, AWAY_TEXT)
            raise ApplicationHandlerStop
        return Person(user_id=user_id, chat=chat.id)

    async def _reply(self, update: Update, text: str) -> None:
        try:
            if update.callback_query is not None:
                await update.callback_query.answer()
            if update.effective_message is not None:
                await update.effective_message.reply_text(text)
        except TelegramError as exc:  # a stale button, the network: the update still stops
            log.warning("bot.gate_reply_failed", error=type(exc).__name__)


def _anywhere(update: Update) -> bool:
    if update.message is None:
        return False
    command = (update.message.text or "").split("@")[0].split(maxsplit=1)
    return bool(command) and command[0] in ANYWHERE
