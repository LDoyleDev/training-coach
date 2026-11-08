"""The sender gate (ADR-0089): the first thing every update meets.

One handler in group -1 decides who an update is from before any other handler runs. It lets
through only a message or a button press, in a private chat whose id is the sender's, from
someone linked in ``users.telegram_user_id``. Strangers, groups, channels and every other kind of
update stop here without a reply, and so does a member while ``TC_MULTI_USER`` is off (ADR-0059).
With it on, a stranger's ``/start <token>`` is the one exception: the gate answers it itself
(``bot.connect``) and still stops it. A button on a message older than the person's link does
nothing, so a chat relinked to someone else can't act with old buttons. Someone away from
Europe for 30 days gets one line (ADR-0085), except for /login and /recover.

A handler registered through ``Gate.served`` gets the ``Person``, with sessions bound to them
(ADR-0029), and does nothing without one.

PTB carries on to the next group when a handler raises anything but ``ApplicationHandlerStop``,
so the gate catches everything and stops: it fails closed. A database error is told only to a
sender it has served before in this process, or to the configured owner account, never to a
stranger.
"""

import functools
from collections import OrderedDict
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

from training_coach.bot.connect import Connect, start_token
from training_coach.bot.messages import SOMETHING_WENT_WRONG
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.consent import Category
from training_coach.services import consent, users

log = structlog.get_logger(__name__)

# The only updates the bot asks Telegram for (start_polling's allowed_updates) and lets in.
ALLOWED_UPDATES = ("message", "callback_query")
AWAY_TEXT = (
    "Training Coach serves the EU and EEA only. Open the website from there to turn me back on."
)
# Still answered when paused: the way back into the website, where a visit from Europe counts.
ANYWHERE = frozenset({"/login", "/recover"})
# Updates whose person the error handler can still look up. The bot handles one update at a
# time (no concurrent_updates, ADR-0089), so no other update passes the gate while a handler
# runs, and a long one (a voice note) can't lose its entry before its error is answered.
REMEMBERED = 256
# What a member is told when a button needs health data they haven't said yes to (ADR-0090).
NOT_OPEN = "That needs your yes to {what} first. You can give it on Account in the app."
WHAT = {
    Category.BODY: "body data",
    Category.DAILY_CHECK: "the daily check",
    Category.BAND: "band data",
}


@dataclass(frozen=True)
class Person:
    """Who an update is from, as the gate found them."""

    user_id: int
    chat: int  # their private chat, which is their Telegram user id
    sessions: sessionmaker[Session] = field(compare=False, repr=False)  # bound to user_id

    @property
    def owner(self) -> bool:
        return self.user_id == users.OWNER

    def not_open(self, category: Category) -> str | None:
        """The line to send when ``category`` isn't open to this person (ADR-0090), or None
        when it is. The owner's categories are always open."""
        if self.owner:
            return None
        with session_scope(self.sessions) as session:
            opened = consent.opened(session, self.user_id, category)
        return None if opened else NOT_OPEN.format(what=WHAT[category])


Callback = Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]
Forget = Callable[[int], None]  # drops what a handler class keeps in memory for a user id
ForPerson = Callable[[Update, ContextTypes.DEFAULT_TYPE, Person], Coroutine[Any, Any, None]]


class Gate:
    def __init__(self, settings: Settings, shared: sessionmaker[Session]) -> None:
        self.settings = settings
        self.shared = shared  # unbound: users is a shared table
        self.seen: set[int] = set()  # Telegram ids served since start-up
        self.found: OrderedDict[int, Person] = OrderedDict()  # update id -> person
        self.bound: dict[int, sessionmaker[Session]] = {}  # user id -> their sessions
        self.connect = Connect(settings, shared)  # a stranger's /start <token> (ADR-0089)
        self.forgets: list[Forget] = []  # every handler class's in-memory state per person

    def keeps(self, forget: Forget) -> None:
        """Register a handler class that keeps state by user id: ``forget`` drops a person's."""
        self.forgets.append(forget)

    def forget(self, user_id: int) -> None:
        """Drop everything kept in memory for ``user_id`` (ADR-0089): after an unlink, a leave
        or an erase, so nothing of theirs is waiting when they, or anyone, come back."""
        for forget in self.forgets:
            forget(user_id)
        self.bound.pop(user_id, None)
        for update_id in [u for u, p in self.found.items() if p.user_id == user_id]:
            del self.found[update_id]

    def served(self, handler: ForPerson) -> Callback:
        """``handler`` with the person this update is from; nothing runs without one. It keeps
        ``handler`` as ``__wrapped__``, so a test can tell a served callback from the rest."""

        @functools.wraps(handler)
        async def run(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
            me = self.person(update)
            if me is not None:
                await handler(update, context, me)

        return run

    def _sessions(self, user_id: int) -> sessionmaker[Session]:
        # One factory per person, made once: each handler still opens short sessions with it.
        if user_id not in self.bound:
            self.bound[user_id] = make_session_factory(self.shared.kw["bind"], user_id=user_id)
        return self.bound[user_id]

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
                linked = None if user_id is None else users.telegram_linked_at(session, user_id)
        except SQLAlchemyError as exc:
            log.error("bot.gate_lookup_failed", error=type(exc).__name__)
            if sender.id in self.seen or sender.id == self.settings.telegram_allowed_user_id:
                await self._reply(update, SOMETHING_WENT_WRONG)
            raise ApplicationHandlerStop from None
        if user_id is None:
            token = start_token(update) if self.settings.multi_user else None
            if token is not None:  # someone connecting their Telegram: a code, nothing more
                text = self.connect.claim(sender.id, sender.first_name, token)
                if text is not None:
                    await self._reply(update, text)
            raise ApplicationHandlerStop  # a stranger
        if users.closed_to(user_id, self.settings.multi_user):
            raise ApplicationHandlerStop  # a member while the switch is off
        if _older_than(update, linked):
            raise ApplicationHandlerStop  # an old button, from before this person's link
        self.seen.add(sender.id)
        if not served and not _anywhere(update):
            await self._reply(update, AWAY_TEXT)
            raise ApplicationHandlerStop
        return Person(user_id=user_id, chat=chat.id, sessions=self._sessions(user_id))

    async def _reply(self, update: Update, text: str) -> None:
        try:
            if update.callback_query is not None:
                await update.callback_query.answer()
            if update.effective_message is not None:
                await update.effective_message.reply_text(text)
        except TelegramError as exc:  # a stale button, the network: the update still stops
            log.warning("bot.gate_reply_failed", error=type(exc).__name__)


def _older_than(update: Update, linked: datetime | None) -> bool:
    """Whether ``update`` is a press on a message sent before ``linked`` (Telegram dates are
    whole seconds). A message Telegram no longer shows has date 0, so it counts as older."""
    press = update.callback_query
    if press is None or linked is None:
        return False
    return press.message is None or press.message.date < linked.replace(microsecond=0)


def _anywhere(update: Update) -> bool:
    if update.message is None:
        return False
    command = (update.message.text or "").split("@")[0].split(maxsplit=1)
    return bool(command) and command[0] in ANYWHERE
