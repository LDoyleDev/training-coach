"""Stretching after a resistance session (#98, ADR-0032).

The "Saved" reply to a resistance log offers 10, 20 or 30 minutes. A choice sends the routine
with a Done button, and Done logs the minutes on that workout. Callback data is
``st:<workout id>:<minutes>`` for a choice and ``st:done:<workout id>:<minutes>`` for Done;
the service re-checks the workout is the owner's saved resistance session.
"""

from dataclasses import dataclass

import structlog
from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.bot.buttons import edit_quietly, row_id
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.stretching import CHOICES, HOLD_SECONDS
from training_coach.services import stretching
from training_coach.services.stretching import Routine

log = structlog.get_logger(__name__)

PREFIX = "st"
GONE = "That workout isn't there any more, so there's nothing to stretch after."
ALREADY = "Stretching is already logged for that workout."


@dataclass(frozen=True)
class Press:
    workout_id: int
    minutes: int
    done: bool = False


def parse(data: str | None) -> Press | None:
    """The button pressed, or None for anything malformed."""
    parts = (data or "").split(":")
    done = len(parts) == 4 and parts[1] == "done"
    if parts[0] != PREFIX or len(parts) != (4 if done else 3):
        return None
    workout_id, minutes = row_id(parts[-2]), row_id(parts[-1])
    if workout_id is None or minutes not in CHOICES:
        return None
    return Press(workout_id, minutes, done)


def rows(workout_id: int) -> list[list[InlineKeyboardButton]]:
    """The choice of time, for the "Saved" reply."""
    return [
        [
            InlineKeyboardButton(
                f"Stretch {minutes} min", callback_data=f"{PREFIX}:{workout_id}:{minutes}"
            )
            for minutes in CHOICES
        ]
    ]


def text(routine: Routine) -> str:
    lines = [
        f"Stretching after {routine.session}, about {routine.minutes} min.",
        f"Hold each stretch {HOLD_SECONDS} s at a gentle pull, 3-4 out of 10, never pain. "
        "Breathe slowly.",
        "",
    ]
    for number, step in enumerate(routine.steps, start=1):
        sides = " each side" if step.stretch.per_side else ""
        lines.append(
            f"{number}. {step.stretch.name}: {step.rounds} rounds of {HOLD_SECONDS} s{sides}"
        )
        lines.append(f"   {step.stretch.cue}")
    lines += ["", "Tap Done when you've finished and I'll add it to the workout."]
    return "\n".join(lines)


class StretchHandlers:
    def __init__(self, settings: Settings, sessions: sessionmaker[Session]) -> None:
        self.settings = settings
        self.sessions = sessions

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """A stretching button. Strangers get nothing, not even an answer (T1)."""
        query = update.callback_query
        user = update.effective_user
        if query is None or user is None or user.id != self.settings.telegram_allowed_user_id:
            return
        press = parse(query.data)
        await query.answer()
        if press is None or not isinstance(query.message, Message):
            return
        if not press.done:
            with session_scope(self.sessions) as session:
                routine = stretching.for_workout(session, press.workout_id, press.minutes)
            if routine is None:
                await query.message.reply_text(GONE)
                return
            done = InlineKeyboardButton(
                "Done", callback_data=f"{PREFIX}:done:{press.workout_id}:{press.minutes}"
            )
            await query.message.reply_text(
                text(routine), reply_markup=InlineKeyboardMarkup([[done]])
            )
            log.info("bot.stretching_shown", minutes=press.minutes, stretches=len(routine.steps))
            return
        with session_scope(self.sessions) as session:
            logged = stretching.log(session, press.workout_id, press.minutes)
        await edit_quietly(query.edit_message_reply_markup(None))
        if logged is None:
            await query.message.reply_text(GONE)
        elif not logged:
            await query.message.reply_text(ALREADY)
        else:
            await query.message.reply_text(f"Added {press.minutes} min of stretching. Nice work.")
        log.info("bot.stretching_logged", minutes=press.minutes, logged=logged)
