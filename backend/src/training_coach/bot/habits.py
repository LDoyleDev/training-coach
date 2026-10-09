"""Habit check-off buttons (D5, #91): one toggle per habit, for the day the message is about.

Callback data is ``h:<YYYYMMDD>:<habit>``. The day travels with the button, so a tap the next
morning still ticks the evening's day; the service refuses days too long ago to change.
The rows can share a message with the morning buttons (``buttons.merged``).
"""

from datetime import UTC, date, datetime

import structlog
from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.bot.buttons import edit_quietly, merged
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.habits import Habit, hint, label
from training_coach.domain.queue import local_date
from training_coach.services import habits, user_settings

log = structlog.get_logger(__name__)

PREFIX = "h"
TOO_LATE = "That day is too long ago to change."
EVENING = "Habits today: tap each one you did."


def _data(day: date, habit: Habit) -> str:
    return f"{PREFIX}:{day:%Y%m%d}:{habit.value}"


def parse(data: str | None) -> tuple[date, Habit] | None:
    """The day and habit a button names, or None for anything malformed."""
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != PREFIX or parts[2] not in set(Habit):
        return None
    digits = parts[1]
    if len(digits) != 8 or not (digits.isascii() and digits.isdecimal()):
        return None
    try:
        day = date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    except ValueError:
        return None
    return day, Habit(parts[2])


def rows(
    day: date, done: frozenset[Habit], protein_g: int | None = None
) -> list[list[InlineKeyboardButton]]:
    """One button per habit; a ticked one shows a check mark."""
    return [
        [
            InlineKeyboardButton(
                f"{'✓ ' if habit in done else ''}{label(habit, protein_g)}",
                callback_data=_data(day, habit),
            )
        ]
        for habit in Habit
    ]


def what_counts(protein_g: int | None = None) -> list[str]:
    """One line per habit saying what counts as done."""
    return [f"- {label(habit, protein_g)}: {hint(habit, protein_g)}" for habit in Habit]


def evening(protein_g: int | None = None) -> str:
    """The habit part of the evening message: what to tick, and what counts."""
    return "\n".join([EVENING, "", *what_counts(protein_g)])


def text(day: date, protein_g: int | None = None) -> str:
    """/habits: today's check-offs with what each one means."""
    lines = [f"Habits for {day:%a %d %b}: tap each one you did.", ""]
    lines += what_counts(protein_g)
    return "\n".join(lines)


class HabitHandlers:
    def __init__(self, settings: Settings, sessions: sessionmaker[Session]) -> None:
        self.settings = settings
        self.sessions = sessions

    def _today(self) -> date:
        return local_date(datetime.now(UTC), self.settings.tz)

    async def command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        today = self._today()
        with session_scope(self.sessions) as session:
            done = habits.checked(session, today)
            protein_g = user_settings.load(session).protein_g
        if update.effective_message is not None:
            await update.effective_message.reply_text(
                text(today, protein_g),
                reply_markup=InlineKeyboardMarkup(rows(today, done, protein_g)),
            )

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """A habit button. Strangers get nothing, not even an answer (T1)."""
        query = update.callback_query
        user = update.effective_user
        if query is None or user is None or user.id != self.settings.telegram_allowed_user_id:
            return
        pressed = parse(query.data)
        if pressed is None or not isinstance(query.message, Message):
            await query.answer()
            return
        day, habit = pressed
        with session_scope(self.sessions) as session:
            state = habits.toggle(session, day, habit, self._today())
            done = habits.checked(session, day)
            protein_g = user_settings.load(session).protein_g
        if state is None:
            await query.answer(TOO_LATE)
            return
        await query.answer()
        markup = merged(query.message.reply_markup, PREFIX, rows(day, done, protein_g))
        await edit_quietly(query.edit_message_reply_markup(markup))
        log.info("bot.habit_toggled", habit=habit.value, done=state)
