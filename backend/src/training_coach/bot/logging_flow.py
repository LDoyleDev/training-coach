"""Typed workout logs: parse, confirm, save (step 1-E; ADR-0007).

Drafts stay in the bot's memory, kept per person (their user id) and keyed by their random
token; buttons carry only ``l:<action>:<token>``, never ids, so a forged press can at most name
a draft that exists, and only among the presser's own.
A restart forgets drafts: the user is asked to send the log again.

A draft for a day that already has its session gets the question first (ADR-0060,
``bot.clash``): its buttons are ``l:<answer>:<token>`` and the answer names the workouts shown.
After Move, a typed date answers it too.
"""

import warnings
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.orm import Session
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update, Voice
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from telegram.warnings import PTBDeprecationWarning

from training_coach.bot import clash as clash_ui
from training_coach.bot import links
from training_coach.bot import progress as progress_ui
from training_coach.bot import stretching as stretching_ui
from training_coach.bot.buttons import edit_quietly
from training_coach.bot.gate import Person
from training_coach.bot.messages import (
    LOG_CANCELLED,
    LOG_EDIT,
    LOG_EXPIRED,
    LOG_SAVED_BEFORE,
    LOG_STALE,
    MODEL_ASSISTED,
    VOICE_CAPPED,
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
from training_coach.domain.dates import date_line
from training_coach.domain.parser import MAX_TEXT, SPLIT_ENTRIES
from training_coach.domain.queue import local_date
from training_coach.services import groq_quota, progress, stretching, workout_log
from training_coach.services.day_clash import MOVE, Clash, Refused, Resolution
from training_coach.services.groq import GroqClient, GroqUnavailableError
from training_coach.services.workout_log import Draft, Saved, Stale

log = structlog.get_logger(__name__)

PREFIX = "l"
ACTIONS = frozenset({"save", "edit", "cancel"})
MAX_DRAFTS = 10  # per person, bounded memory: only their most recent drafts can be saved
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
    if len(parts) != 3 or parts[0] != PREFIX:
        return None
    if parts[1] not in ACTIONS and not clash_ui.is_answer(parts[1]):
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
    """Each handler gets the person the gate found and works in their sessions only."""

    def __init__(self, settings: Settings, groq: GroqClient | None = None) -> None:
        self.settings = settings
        self.groq = groq  # None until TC_GROQ_API_KEY is set: voice notes get the typed fallback
        # User id -> that person's drafts: one person's logs never push out another's.
        self.drafts: dict[int, OrderedDict[str, Draft]] = {}
        # User id -> draft token -> the clash shown for it, and a day to move to that was
        # found taken (ADR-0060); and the draft waiting for a typed date after Move.
        self.asked: dict[int, dict[str, tuple[Clash, date | None]]] = {}
        self.moving: dict[int, str] = {}

    def forget(self, user_id: int) -> None:
        """Drop ``user_id``'s drafts and questions (``Gate.forget``)."""
        for kept in (self.drafts, self.asked, self.moving):
            kept.pop(user_id, None)

    def _today(self) -> date:
        return local_date(datetime.now(UTC), self.settings.tz)

    def _remember(self, author: int, draft: Draft) -> None:  # author: a user id
        mine = self.drafts.setdefault(author, OrderedDict())
        mine[draft.token] = draft
        while len(mine) > MAX_DRAFTS:
            gone, _ = mine.popitem(last=False)
            self.asked.get(author, {}).pop(gone, None)

    async def message(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person
    ) -> None:
        """Plain text from someone the gate let through."""
        message = update.effective_message
        if message is None or not message.text:
            return
        if await self._typed_move(message, me, message.text):
            return
        await self._draft_and_confirm(message, me, message.text)

    async def _typed_move(self, message: Message, me: Person, text: str) -> bool:
        """A date sent after Move answers the question; anything else is a new log."""
        author = me.user_id
        token = self.moving.pop(author, None)
        if token is None:
            return False
        draft = self.drafts.get(author, OrderedDict()).get(token)
        asked = self.asked.get(author, {}).get(token)
        if draft is None or asked is None:
            return False
        found = clash_ui.typed_move(text, asked[0], self._today())
        if found is None:
            return False
        if isinstance(found, str):
            self.moving[author] = token  # still waiting for a date
            await message.reply_text(f"{found}. Send another date, or tap a day.")
            return True
        reply, markup = self._save(me, draft, found)
        await message.reply_text(reply, reply_markup=markup)
        return True

    async def voice(self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        """A voice note: transcribe, then the same confirm flow as text.

        The audio is downloaded into memory only, never to disk, and the transcript is shown
        to the person but never logged (ADR-0008, threat model).
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
        with session_scope(me.sessions) as session:
            vocabulary = workout_log.exercise_names(session)
            allowed = groq_quota.left(session, datetime.now(UTC), self.settings.tz)
        if not allowed:
            await message.reply_text(VOICE_CAPPED)
            return
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
        with session_scope(me.sessions) as session:
            # Groq answered: one of today's uses. Two notes at once can both pass the check
            # before either counts, so the cap can be passed by a note or two: fine for fairness.
            groq_quota.count(session, datetime.now(UTC))
        if not heard:
            await message.reply_text(VOICE_FAILED)
            return
        log.info("bot.voice_transcribed", seconds=seconds)
        await self._draft_and_confirm(message, me, heard, heard=heard)

    async def _draft_and_confirm(
        self, message: Message, me: Person, text: str, heard: str | None = None
    ) -> None:
        with session_scope(me.sessions) as session:
            draft = workout_log.draft(session, text, self._today(), self.settings.tz)
            names = workout_log.exercise_labels(session)
        assisted = False
        # A date line never goes to the model: it reads the log under it, and its reading is
        # put back under the same line. A refused date isn't sent at all (#104).
        first, _, body = text.partition("\n")
        dated = date_line(first, self._today())
        with session_scope(me.sessions) as session:  # a date or a session's name on top
            head = workout_log.heading(session, first, self._today())
        if (
            draft.problems
            and len(text) <= MAX_TEXT
            and not draft.rest
            and not isinstance(dated, str)
        ):
            model_draft = await self._model_reading(
                me,
                body if head else text,
                [name for name, _ in names.values()],
                heading=first if head else None,
            )
            # Exact rule readings are never overwritten: the model may only fill the gaps.
            if (
                model_draft is not None
                and model_draft.on == draft.on
                and set(draft.entries) <= set(model_draft.entries)
            ):
                draft, assisted = model_draft, True
        markup = None
        if draft.entries or (draft.rest and not draft.problems):
            self._remember(me.user_id, draft)
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

    async def _model_reading(
        self, me: Person, text: str, names: list[str], heading: str | None = None
    ) -> Draft | None:
        """The language model's reading, used only when it reads cleanly (ADR-0007, 0008).

        Its output is never data: it becomes plain log text, which the same rule parser must
        accept with no problems at all, and the person still confirms before anything is saved.
        """
        if self.groq is None:
            return None
        with session_scope(me.sessions) as session:
            allowed = groq_quota.left(session, datetime.now(UTC), self.settings.tz)
        if not allowed:  # today's uses of the shared key are spent: the rule parser's reading
            return None
        try:
            rewrite = await self.groq.rewrite_log(text, names=names)
        except GroqUnavailableError as exc:
            log.warning("bot.model_fallback_failed", reason=exc.reason)
            return None
        with session_scope(me.sessions) as session:
            groq_quota.count(session, datetime.now(UTC))
        model_text = workout_log.rewrite_text(rewrite)
        if not model_text:
            return None
        with session_scope(me.sessions) as session:
            reread_text = f"{heading}\n{model_text}" if heading is not None else model_text
            reread = workout_log.draft(session, reread_text, self._today(), self.settings.tz)
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

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        """Save / Edit / Cancel, on the presser's own drafts only."""
        query = update.callback_query
        if query is None:
            return
        author = me.user_id
        press = parse(query.data)
        await query.answer()
        if press is None or not isinstance(query.message, Message):
            return
        # Saved drafts stay (bounded by MAX_DRAFTS) so a second Save tap answers "already
        # saved" from the database instead of "expired", which would invite a duplicate.
        mine = self.drafts.get(author, OrderedDict())
        draft = mine.get(press.token)
        markup = None
        if press.action == "save":
            reply, markup = (LOG_EXPIRED, None) if draft is None else self._save(me, draft)
        elif press.action != "cancel" and clash_ui.is_answer(press.action):
            found = self.asked.get(author, {}).get(press.token)
            if draft is None or found is None:
                reply = LOG_EXPIRED
            else:
                reply, markup = self._answer(me, draft, press.action, found)
        else:
            self.moving.pop(author, None)
            mine.pop(press.token, None)
            self.asked.get(author, {}).pop(press.token, None)
            reply = LOG_CANCELLED if press.action == "cancel" else LOG_EDIT
        # Act first, then retire the buttons: if the edit fails, the outcome already stands
        # and a retry answers "already saved".
        await edit_quietly(query.edit_message_reply_markup(None))
        await query.message.reply_text(reply, reply_markup=markup)

    def _answer(
        self, me: Person, draft: Draft, action: str, found: tuple[Clash, date | None]
    ) -> tuple[str, InlineKeyboardMarkup | None]:
        """An answer to the question: Move shows the days to pick; the rest save with it."""
        clash, taken = found
        if action == MOVE:
            self.moving[me.user_id] = draft.token
            keyboard = clash_ui.days_keyboard(PREFIX, draft.token, clash, self._today(), taken)
            return clash_ui.MOVE_ASK, keyboard
        answer = clash_ui.resolution(action, clash, self._today())
        return self._save(me, draft, answer)

    def _asked(
        self, author: int, draft: Draft, result: Clash | Refused, answer: Resolution | None
    ) -> tuple[str, InlineKeyboardMarkup]:
        """The question (again), or the days to move to when the one picked was taken."""
        mine = self.asked.setdefault(author, {})
        shown = mine.get(draft.token)
        if isinstance(result, Refused) or result.moving:
            assert shown is not None  # noqa: S101 - only an answer to a question gets these
            taken = result.day if isinstance(result, Clash) else shown[1]
            mine[draft.token] = (shown[0], taken)
            self.moving[author] = draft.token
            keyboard = clash_ui.days_keyboard(PREFIX, draft.token, shown[0], self._today(), taken)
            why = clash_ui.taken_text(result) if isinstance(result, Clash) else result.reason
            return f"{why}\n\n{clash_ui.MOVE_ASK}", keyboard
        mine[draft.token] = (result, None)
        one = len(result.recorded) == 1
        reply = clash_ui.text(result)
        if answer is not None:
            reply = f"{clash_ui.CHANGED}\n\n{reply}"
        return reply, clash_ui.keyboard(PREFIX, draft.token, one)

    def _save(
        self, me: Person, draft: Draft, answer: Resolution | None = None
    ) -> tuple[str, InlineKeyboardMarkup | None]:
        """The saved reply, with bests, any "ready to progress" prompts (1-G) and "Open in
        app" (C1); or the question, when the day already has its session (ADR-0060)."""
        author = me.user_id
        markup: InlineKeyboardMarkup | None = None
        with session_scope(me.sessions) as session:
            result = workout_log.save(session, draft, self.settings.tz, answer)
            if isinstance(result, Clash | Refused):
                text, markup = self._asked(author, draft, result, answer)
            elif isinstance(result, Saved) and not result.already_saved:
                text = log_saved_text(
                    sets=sum(len(e.sets) for e in draft.entries),
                    exercises=len(draft.entries),
                    session=draft.session_name,
                    next_session=workout_log.next_session_name(session),
                    on=draft.on if draft.backdated else None,
                )
                earned = _feedback(session, result.workout_id, self.settings.tz)
                text = saved_reply(text, earned)
                markup = progress_ui.keyboard(earned)
                if not draft.backdated and stretching.offered(session, result.workout_id):
                    rows = [
                        *(markup.inline_keyboard if markup else ()),
                        *stretching_ui.rows(result.workout_id),
                    ]
                    markup = InlineKeyboardMarkup(rows)
                markup = links.with_open(markup, self.settings.public_url, links.HOME)
            elif isinstance(result, Saved):
                text = LOG_SAVED_BEFORE
            elif isinstance(result, Stale):
                text = LOG_STALE
            else:  # nothing to save; the draft had no entries (no buttons are sent for those)
                text = LOG_EXPIRED
        if not isinstance(result, Clash | Refused):
            self.asked.get(author, {}).pop(draft.token, None)
            self.moving.pop(author, None)
        log.info("bot.log_saved", outcome=type(result).__name__)
        return text, markup
