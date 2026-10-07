"""Typed workout logs: parse, confirm, save (step 1-E; ADR-0007).

Drafts stay in the bot's memory keyed by their random token; buttons carry only
``l:<action>:<token>``, never ids, so a forged press can at most name a draft that exists.
A restart forgets drafts: the user is asked to send the log again.
"""

import warnings
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update, Voice
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telegram.warnings import PTBDeprecationWarning

from training_coach.bot import progress as progress_ui
from training_coach.bot.buttons import edit_quietly
from training_coach.bot.messages import (
    LOG_CANCELLED,
    LOG_EDIT,
    LOG_EXPIRED,
    LOG_SAVED_BEFORE,
    LOG_STALE,
    MODEL_ASSISTED,
    VOICE_FAILED,
    VOICE_OFF,
    VOICE_TOO_LONG,
    heard_text,
    log_saved_text,
    log_text,
    saved_reply,
)
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.parser import MAX_TEXT, SPLIT_ENTRIES
from training_coach.domain.queue import local_date
from training_coach.services import progress, workout_log
from training_coach.services.groq import GroqClient, GroqUnavailableError
from training_coach.services.workout_log import Draft, Saved, Stale

log = structlog.get_logger(__name__)

PREFIX = "l"
ACTIONS = frozenset({"save", "edit", "cancel"})
MAX_DRAFTS = 10  # bounded memory: only the most recent drafts can be saved
TOKEN_LENGTH = 32
MAX_VOICE_SECONDS = 120
MAX_VOICE_BYTES = 5 * 1024 * 1024


def _feedback(session: Session, workout_id: int, tz: ZoneInfo) -> list[progress.Feedback]:
    """Bests and prompts for a saved workout. In a savepoint and never raising: a bug here
    must not roll back the save, or every later log would fail the same way."""
    try:
        with session.begin_nested():
            return progress.feedback(session, workout_id, tz)
    except Exception as exc:
        log.error("bot.feedback_failed", error=type(exc).__name__)
        return []


def _seconds(voice: Voice) -> float:
    """``Voice.duration`` is an int today and a timedelta in a future PTB; accept both."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PTBDeprecationWarning)
        duration = voice.duration
    return duration.total_seconds() if isinstance(duration, timedelta) else float(duration)


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
    def __init__(
        self, settings: Settings, sessions: sessionmaker[Session], groq: GroqClient | None = None
    ) -> None:
        self.settings = settings
        self.sessions = sessions
        self.groq = groq  # None until TC_GROQ_API_KEY is set: voice notes get the typed fallback
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
        await self._draft_and_confirm(message, message.text)

    async def voice(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """A voice note from the owner: transcribe, then the same confirm flow as text.

        The audio is downloaded into memory only, never to disk, and the transcript is shown
        to the owner but never logged (ADR-0008, threat model).
        """
        message = update.effective_message
        if message is None or message.voice is None:
            return
        if self.groq is None:
            await message.reply_text(VOICE_OFF)
            return
        voice = message.voice
        seconds = _seconds(voice)
        if seconds > MAX_VOICE_SECONDS or (voice.file_size or 0) > MAX_VOICE_BYTES:
            await message.reply_text(VOICE_TOO_LONG)
            return
        with session_scope(self.sessions) as session:
            vocabulary = workout_log.exercise_names(session)
        try:
            file = await voice.get_file()
            # The Bot API may omit a size; never download something of unknown size.
            size = voice.file_size or file.file_size
            if size is None or size > MAX_VOICE_BYTES:
                await message.reply_text(VOICE_TOO_LONG if size else VOICE_FAILED)
                return
            audio = bytes(await file.download_as_bytearray())
            heard = await self.groq.transcribe(audio, vocabulary=vocabulary)
        except (GroqUnavailableError, TelegramError) as exc:
            log.warning("bot.voice_failed", error=type(exc).__name__)
            await message.reply_text(VOICE_FAILED)
            return
        if not heard:
            await message.reply_text(VOICE_FAILED)
            return
        log.info("bot.voice_transcribed", seconds=seconds)
        await self._draft_and_confirm(message, heard, heard=heard)

    async def _draft_and_confirm(
        self, message: Message, text: str, heard: str | None = None
    ) -> None:
        with session_scope(self.sessions) as session:
            draft = workout_log.draft(session, text, self._today(), self.settings.tz)
            names = workout_log.exercise_labels(session)
        assisted = False
        if draft.problems and len(text) <= MAX_TEXT:
            model_draft = await self._model_reading(text, [name for name, _ in names.values()])
            # Exact rule readings are never overwritten: the model may only fill the gaps.
            if model_draft is not None and set(draft.entries) <= set(model_draft.entries):
                draft, assisted = model_draft, True
        markup = None
        if draft.entries:
            self._remember(draft)
            markup = keyboard(draft.token)
        log.info(
            "bot.log_drafted",
            entries=len(draft.entries),
            problems=len(draft.problems),
            assisted=assisted,
        )
        reply = log_text(draft, names)
        if assisted:
            reply = f"{MODEL_ASSISTED}\n\n{reply}"
        if heard is not None:
            reply = f"{heard_text(heard)}\n\n{reply}"
        await message.reply_text(reply, reply_markup=markup)

    async def _model_reading(self, text: str, names: list[str]) -> Draft | None:
        """The language model's reading, used only when it reads cleanly (ADR-0007, 0008).

        Its output is never data: it becomes plain log text, which the same rule parser must
        accept with no problems at all, and the owner still confirms before anything is saved.
        """
        if self.groq is None:
            return None
        try:
            rewrite = await self.groq.rewrite_log(text, names=names)
        except GroqUnavailableError as exc:
            log.warning("bot.model_fallback_failed", reason=exc.reason)
            return None
        model_text = workout_log.rewrite_text(rewrite)
        if not model_text:
            return None
        with session_scope(self.sessions) as session:
            reread = workout_log.draft(session, model_text, self._today(), self.settings.tz)
        if not reread.entries or reread.problems:
            log.info("bot.model_fallback_rejected", problems=len(reread.problems))
            return None
        # The model leaves out what it can't place; say so rather than drop it silently.
        parts = len([chunk for chunk in SPLIT_ENTRIES.split(text) if chunk.strip()])
        if len(reread.entries) < parts:
            note = (
                f"The model read {len(reread.entries)} of {parts} parts of your message; "
                "check nothing is missing."
            )
            return replace(reread, problems=(note,))
        return reread

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
        markup = None
        if press.action == "save":
            reply, markup = (LOG_EXPIRED, None) if draft is None else self._save(draft)
        else:
            self.drafts.pop(press.token, None)
            reply = LOG_CANCELLED if press.action == "cancel" else LOG_EDIT
        # Act first, then retire the buttons: if the edit fails, the outcome already stands
        # and a retry answers "already saved".
        await edit_quietly(query.edit_message_reply_markup(None))
        await query.message.reply_text(reply, reply_markup=markup)

    def _save(self, draft: Draft) -> tuple[str, InlineKeyboardMarkup | None]:
        """The saved reply, with bests and any "ready to progress" prompts (1-G)."""
        markup = None
        with session_scope(self.sessions) as session:
            result = workout_log.save(session, draft, self.settings.tz)
            if isinstance(result, Saved) and not result.already_saved:
                text = log_saved_text(
                    sets=sum(len(e.sets) for e in draft.entries),
                    exercises=len(draft.entries),
                    session=draft.session_name,
                    next_session=workout_log.next_session_name(session),
                )
                earned = _feedback(session, result.workout_id, self.settings.tz)
                text = saved_reply(text, earned)
                markup = progress_ui.keyboard(earned)
            elif isinstance(result, Saved):
                text = LOG_SAVED_BEFORE
            elif isinstance(result, Stale):
                text = LOG_STALE
            else:  # nothing to save; the draft had no entries (no buttons are sent for those)
                text = LOG_EXPIRED
        log.info("bot.log_saved", outcome=type(result).__name__)
        return text, markup
