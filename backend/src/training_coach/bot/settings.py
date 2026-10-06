"""/settings: morning and nudge times, nudges on/off, pause.

Callback data is ``s:<what>[:<HHMM>]``. A typed time (after "Other time...") is only read
while the bot is waiting for one; otherwise plain text is left for logging (step 1-E).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import time

import structlog
from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.clock import parse_hhmm
from training_coach.services import user_settings
from training_coach.services.user_settings import Prefs

log = structlog.get_logger(__name__)

PREFIX = "s"
MORNING_PRESETS = (time(6, 30), time(7, 0), time(7, 30), time(8, 0))
NUDGE_PRESETS = (time(19, 0), time(20, 0), time(21, 0))
AWAITING = "awaiting_time"  # key in context.user_data: "morning" or "nudge"
BAD_TIME = "That isn't a time like 07:30. Send it again, or /settings to cancel."

Reschedule = Callable[[ContextTypes.DEFAULT_TYPE, Prefs], None]


@dataclass(frozen=True)
class Press:
    what: str  # morning | nudge | ask-morning | ask-nudge | nudges | pause
    at: time | None = None


def _hhmm(t: time) -> str:
    return f"{t:%H:%M}"


def _data(what: str, at: time | None = None) -> str:
    return f"{PREFIX}:{what}" + (f":{at:%H%M}" if at is not None else "")


def parse(data: str | None) -> Press | None:
    parts = (data or "").split(":")
    if (
        len(parts) == 2
        and parts[0] == PREFIX
        and parts[1]
        in {
            "ask-morning",
            "ask-nudge",
            "nudges",
            "pause",
        }
    ):
        return Press(parts[1])
    if len(parts) == 3 and parts[0] == PREFIX and parts[1] in {"morning", "nudge"}:
        at = parse_hhmm(f"{parts[2][:2]}:{parts[2][2:]}") if len(parts[2]) == 4 else None
        return Press(parts[1], at) if at is not None else None
    return None


def text(prefs: Prefs) -> str:
    nudge = "on" if prefs.nudges_enabled else "off"
    return "\n".join(
        [
            "Settings",
            "",
            f"Morning message: {_hhmm(prefs.morning_time)}",
            f"Evening nudge: {_hhmm(prefs.nudge_time)} ({nudge})",
            f"Paused: {'yes, no messages until you resume' if prefs.paused else 'no'}",
        ]
    )


def _mark(t: time, current: time) -> str:
    return f"{'• ' if t == current else ''}{_hhmm(t)}"


def keyboard(prefs: Prefs) -> InlineKeyboardMarkup:
    button = InlineKeyboardButton
    return InlineKeyboardMarkup(
        [
            [
                button(_mark(t, prefs.morning_time), callback_data=_data("morning", t))
                for t in MORNING_PRESETS
            ],
            [button("Morning: other time…", callback_data=_data("ask-morning"))],
            [
                button(_mark(t, prefs.nudge_time), callback_data=_data("nudge", t))
                for t in NUDGE_PRESETS
            ],
            [
                button("Nudge: other time…", callback_data=_data("ask-nudge")),
                button(
                    "Turn nudges off" if prefs.nudges_enabled else "Turn nudges on",
                    callback_data=_data("nudges"),
                ),
            ],
            [button("Resume" if prefs.paused else "Pause", callback_data=_data("pause"))],
        ]
    )


class SettingsHandlers:
    def __init__(
        self, settings: Settings, sessions: sessionmaker[Session], reschedule: Reschedule
    ) -> None:
        self.settings = settings
        self.sessions = sessions
        self.reschedule = reschedule

    def _is_owner(self, update: Update) -> bool:
        user = update.effective_user
        return user is not None and user.id == self.settings.telegram_allowed_user_id

    async def command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.user_data is not None:
            context.user_data.pop(AWAITING, None)
        with session_scope(self.sessions) as session:
            prefs = user_settings.load(session)
        if update.effective_message is not None:
            await update.effective_message.reply_text(text(prefs), reply_markup=keyboard(prefs))

    async def button(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """A /settings button. Strangers get nothing, not even an answer (T1)."""
        query = update.callback_query
        if query is None or not self._is_owner(update):
            return
        press = parse(query.data)
        await query.answer()
        if press is None or not isinstance(query.message, Message):
            return
        if press.what in ("ask-morning", "ask-nudge"):
            which = press.what.removeprefix("ask-")
            if context.user_data is not None:
                context.user_data[AWAITING] = which
            await query.message.reply_text(f"Send the {which} time as HH:MM, for example 07:15.")
            return
        with session_scope(self.sessions) as session:
            current = user_settings.load(session)
            prefs = user_settings.update(
                session,
                morning_time=press.at if press.what == "morning" else None,
                nudge_time=press.at if press.what == "nudge" else None,
                nudges_enabled=not current.nudges_enabled if press.what == "nudges" else None,
                paused=not current.paused if press.what == "pause" else None,
            )
        if press.what in ("morning", "nudge"):
            self.reschedule(context, prefs)
        log.info("bot.settings_changed", what=press.what)
        await query.edit_message_text(text(prefs), reply_markup=keyboard(prefs))

    async def typed_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Plain text from the owner: a time, if one was asked for."""
        message = update.effective_message
        which = context.user_data.get(AWAITING) if context.user_data is not None else None
        if message is None or which not in ("morning", "nudge"):
            return
        at = parse_hhmm(message.text or "")
        if at is None:
            await message.reply_text(BAD_TIME)
            return
        assert context.user_data is not None  # noqa: S101 - read above
        context.user_data.pop(AWAITING, None)
        with session_scope(self.sessions) as session:
            if which == "morning":
                prefs = user_settings.update(session, morning_time=at)
            else:
                prefs = user_settings.update(session, nudge_time=at)
        self.reschedule(context, prefs)
        log.info("bot.settings_changed", what=which)
        await message.reply_text(text(prefs), reply_markup=keyboard(prefs))
