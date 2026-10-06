"""Typed workout logs: parse, confirm, save (step 1-E; ADR-0007).

Drafts stay in the bot's memory keyed by their random token; buttons carry only
``l:<action>:<token>``, never ids, so a forged press can at most name a draft that exists.
A restart forgets drafts: the user is asked to send the log again.
"""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, date, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.bot.buttons import edit_quietly
from training_coach.bot.messages import (
    LOG_CANCELLED,
    LOG_EDIT,
    LOG_EXPIRED,
    LOG_SAVED_BEFORE,
    LOG_STALE,
    log_saved_text,
    log_text,
)
from training_coach.config import Settings
from training_coach.db.models import Exercise, SessionTemplate
from training_coach.db.session import session_scope
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.queue import local_date
from training_coach.services import workout_log
from training_coach.services.today import position
from training_coach.services.workout_log import Draft, Saved, Stale

log = structlog.get_logger(__name__)

PREFIX = "l"
ACTIONS = frozenset({"save", "edit", "cancel"})
MAX_DRAFTS = 10  # bounded memory: only the most recent drafts can be saved
TOKEN_LENGTH = 32


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


def keyboard(token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Save", callback_data=f"{PREFIX}:save:{token}"),
                InlineKeyboardButton("Edit", callback_data=f"{PREFIX}:edit:{token}"),
                InlineKeyboardButton("Cancel", callback_data=f"{PREFIX}:cancel:{token}"),
            ]
        ]
    )


class LogHandlers:
    def __init__(self, settings: Settings, sessions: sessionmaker[Session]) -> None:
        self.settings = settings
        self.sessions = sessions
        self.drafts: OrderedDict[str, Draft] = OrderedDict()

    def _today(self) -> date:
        return local_date(datetime.now(UTC), self.settings.tz)

    def _remember(self, draft: Draft) -> None:
        self.drafts[draft.token] = draft
        while len(self.drafts) > MAX_DRAFTS:
            self.drafts.popitem(last=False)

    async def message(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """Plain text from the owner (the handler's filter already checked the sender)."""
        message = update.effective_message
        if message is None or not message.text:
            return
        with session_scope(self.sessions) as session:
            draft = workout_log.draft(session, message.text, self._today(), self.settings.tz)
            names = {
                e.slug: (e.name, ExerciseKind(e.kind)) for e in session.scalars(select(Exercise))
            }
        markup = None
        if draft.entries:
            self._remember(draft)
            markup = keyboard(draft.token)
        log.info("bot.log_drafted", entries=len(draft.entries), problems=len(draft.problems))
        await message.reply_text(log_text(draft, names), reply_markup=markup)

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """Save / Edit / Cancel. Strangers get nothing, not even an answer (T1)."""
        query = update.callback_query
        user = update.effective_user
        if query is None or user is None or user.id != self.settings.telegram_allowed_user_id:
            return
        press = parse(query.data)
        await query.answer()
        if press is None or not isinstance(query.message, Message):
            return
        # Saved drafts stay (bounded by MAX_DRAFTS) so a second Save tap answers "already
        # saved" from the database instead of "expired", which would invite a duplicate.
        draft = self.drafts.get(press.token)
        await edit_quietly(
            query.edit_message_reply_markup(None)
        )  # every outcome retires these buttons
        if press.action == "cancel":
            self.drafts.pop(press.token, None)
            await query.message.reply_text(LOG_CANCELLED)
            return
        if press.action == "edit":
            self.drafts.pop(press.token, None)
            await query.message.reply_text(LOG_EDIT)
            return
        if draft is None:
            await query.message.reply_text(LOG_EXPIRED)
            return
        await query.message.reply_text(self._save(draft))

    def _save(self, draft: Draft) -> str:
        with session_scope(self.sessions) as session:
            result = workout_log.save(session, draft, self.settings.tz)
            if isinstance(result, Saved) and not result.already_saved:
                current = position(session)
                upcoming = session.get(SessionTemplate, current.pointer) if current else None
                text = log_saved_text(
                    sets=sum(len(e.sets) for e in draft.entries),
                    exercises=len(draft.entries),
                    session=draft.session_name,
                    next_session=upcoming.name if upcoming is not None else None,
                )
            elif isinstance(result, Saved):
                text = LOG_SAVED_BEFORE
            elif isinstance(result, Stale):
                text = LOG_STALE
            else:  # nothing to save; the draft had no entries (no buttons are sent for those)
                text = LOG_EXPIRED
        log.info("bot.log_saved", outcome=type(result).__name__)
        return text
