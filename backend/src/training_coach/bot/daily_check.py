"""The daily check on the morning message (ADR-0053): sleep, soreness and energy as three rows
of buttons under the session, until answered today.

Callback data is ``d:<YYYYMMDD>:<sleep>:<soreness>:<energy>``, ``-`` for a row not tapped yet:
each button carries the answers so far plus its own, so nothing is kept between taps. The day
travels with the button, so yesterday's message can't answer today. Once all three are tapped
the answers are saved (the same service as the web app) and the bot replies with the advice,
and Rest today (the morning buttons' rest, ADR-0022) when it says to rest.
"""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

import structlog
from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.bot import buttons
from training_coach.bot.buttons import edit_quietly, merged
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.daily_check import (
    TEXTS,
    Advice,
    Answers,
    Energy,
    Sleep,
    Soreness,
    advise,
    summary,
)
from training_coach.domain.queue import local_date
from training_coach.services import daily_check
from training_coach.services.today import today as todays_session

log = structlog.get_logger(__name__)

PREFIX = "d"
ASK = "How's today? Tap one in each row and I'll say how hard to go."
OLD = "That check was for another day."
UNSET = "-"

# Button labels, row by row (best first, as the questions go).
LABELS: tuple[tuple[tuple[str, str], ...], ...] = (
    ((Sleep.GOOD, "Slept well"), (Sleep.OK, "Slept OK"), (Sleep.POOR, "Slept poorly")),
    ((Soreness.NONE, "Not sore"), (Soreness.SOME, "A bit sore"), (Soreness.A_LOT, "Very sore")),
    ((Energy.HIGH, "High energy"), (Energy.NORMAL, "Normal"), (Energy.LOW, "Low energy")),
)
KINDS = (Sleep, Soreness, Energy)


@dataclass(frozen=True)
class Tap:
    day: date
    picked: tuple[str | None, str | None, str | None]  # sleep, soreness, energy so far


def _data(tap: Tap) -> str:
    parts = [value or UNSET for value in tap.picked]
    return ":".join([PREFIX, f"{tap.day:%Y%m%d}", *parts])


def parse(data: str | None) -> Tap | None:
    """The day and answers a button names, or None for anything malformed."""
    parts = (data or "").split(":")
    if len(parts) != 5 or parts[0] != PREFIX:
        return None
    digits = parts[1]
    if len(digits) != 8 or not (digits.isascii() and digits.isdecimal()):
        return None
    try:
        day = date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    except ValueError:
        return None
    picked: list[str | None] = []
    for value, kind in zip(parts[2:], KINDS, strict=True):
        if value != UNSET and value not in set(kind):
            return None
        picked.append(None if value == UNSET else value)
    return Tap(day, (picked[0], picked[1], picked[2]))


def rows(tap: Tap) -> list[list[InlineKeyboardButton]]:
    """One row per question; a tapped answer shows a check mark, and each button carries the
    answers so far with its own."""
    out = []
    for index, options in enumerate(LABELS):
        row = []
        for value, label in options:
            picked = list(tap.picked)
            picked[index] = value
            mark = "✓ " if tap.picked[index] == value else ""
            after = replace(tap, picked=(picked[0], picked[1], picked[2]))
            row.append(InlineKeyboardButton(f"{mark}{label}", callback_data=_data(after)))
        out.append(row)
    return out


def ask(day: date) -> list[list[InlineKeyboardButton]]:
    """The rows for a fresh morning message."""
    return rows(Tap(day, (None, None, None)))


def with_check(markup: InlineKeyboardMarkup, day: date) -> InlineKeyboardMarkup:
    """``markup`` with the check's rows added, above an "Open in app" row if there is one."""
    rows = [list(row) for row in markup.inline_keyboard]
    at = len(rows) - 1 if rows and rows[-1][0].url is not None else len(rows)
    return InlineKeyboardMarkup([*rows[:at], *ask(day), *rows[at:]])


def _complete(tap: Tap) -> Answers | None:
    sleep, soreness, energy = tap.picked
    if sleep is None or soreness is None or energy is None:
        return None
    return Answers(Sleep(sleep), Soreness(soreness), Energy(energy))


class DailyCheckHandlers:
    def __init__(self, settings: Settings, sessions: sessionmaker[Session]) -> None:
        self.settings = settings
        self.sessions = sessions

    def _today(self) -> date:
        return local_date(datetime.now(UTC), self.settings.tz)

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """A daily-check button. Strangers get nothing, not even an answer (T1)."""
        query = update.callback_query
        user = update.effective_user
        if query is None or user is None or user.id != self.settings.telegram_allowed_user_id:
            return
        tap = parse(query.data)
        if tap is None or not isinstance(query.message, Message):
            await query.answer()
            return
        current = query.message.reply_markup
        if tap.day != self._today():
            await query.answer(OLD)
            await edit_quietly(query.edit_message_reply_markup(merged(current, PREFIX, [])))
            return
        answers = _complete(tap)
        if answers is None:  # another row to go: show the tap
            await query.answer()
            await edit_quietly(query.edit_message_reply_markup(merged(current, PREFIX, rows(tap))))
            return
        advice = advise(answers)
        rest = None
        with session_scope(self.sessions) as session:
            daily_check.save(session, tap.day, answers, datetime.now(UTC))
            if advice is Advice.REST:
                plan = todays_session(session, tap.day, self.settings.tz)
                if plan is not None and plan.test_day is None:
                    rest = plan.session.template_id
        await query.answer()
        await edit_quietly(query.edit_message_reply_markup(merged(current, PREFIX, [])))
        markup = None
        if rest is not None:
            markup = InlineKeyboardMarkup([[buttons.rest_button(rest)]])
        await query.message.reply_text(
            f"{summary(answers)}.\n\n{TEXTS[advice]}", reply_markup=markup
        )
        log.info("bot.daily_check_saved")
