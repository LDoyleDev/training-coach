"""The "ready to progress" prompt: Move up / Not yet (step 1-G; ADR-0016, ADR-0025).

Buttons carry ``p:<up|no>:<exercise id>:<step id>``. The service checks everything again on a
press, so a stale or forged press can at most get an "already moved" answer.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.bot.buttons import edit_quietly, row_id
from training_coach.bot.messages import progress_text
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.progression import Progress
from training_coach.services import progress
from training_coach.services.progress import Feedback, MoveOutcome, Standing

PREFIX = "p"


@dataclass(frozen=True)
class Press:
    action: str  # "up" or "no"
    exercise_id: int
    step_id: int


def parse(data: str | None) -> Press | None:
    parts = (data or "").split(":")
    if len(parts) != 4 or parts[0] != PREFIX or parts[1] not in {"up", "no"}:
        return None
    exercise_id, step_id = row_id(parts[2]), row_id(parts[3])
    if exercise_id is None or step_id is None:
        return None
    return Press(parts[1], exercise_id, step_id)


def _row(item: Feedback | Standing) -> list[InlineKeyboardButton]:
    ids = f"{item.exercise_id}:{item.step_id}"
    return [
        InlineKeyboardButton(f"Move up: {item.exercise}", callback_data=f"{PREFIX}:up:{ids}"),
        InlineKeyboardButton("Not yet", callback_data=f"{PREFIX}:no:{ids}"),
    ]


def keyboard(items: Sequence[Feedback | Standing]) -> InlineKeyboardMarkup | None:
    rows = [_row(item) for item in items if item.status is Progress.READY]
    return InlineKeyboardMarkup(rows) if rows else None


def _without(markup: InlineKeyboardMarkup | None, press: Press) -> InlineKeyboardMarkup | None:
    """The prompt's buttons minus the answered exercise's row; other prompts stay."""
    if markup is None:
        return None
    ids = f":{press.exercise_id}:{press.step_id}"
    rows = [
        list(row)
        for row in markup.inline_keyboard
        if not any(str(b.callback_data or "").endswith(ids) for b in row)
    ]
    return InlineKeyboardMarkup(rows) if rows else None


def reply(outcome: progress.Move | None) -> str:
    if outcome is None:
        return "That exercise isn't in the plan any more."
    name = outcome.exercise
    if outcome.outcome is MoveOutcome.MOVED:
        return (
            f"Moved up: {name} is now {outcome.step}. "
            "Targets start again at the bottom of the range."
        )
    if outcome.outcome is MoveOutcome.ALREADY_MOVED:
        return f"{name} has already moved on since that message."
    if outcome.outcome is MoveOutcome.NO_NEXT_STEP:
        return f"{name} is on the last step in your plan."
    return f"{name} doesn't meet the rule any more. Keep going."


class ProgressHandlers:
    def __init__(self, settings: Settings, sessions: sessionmaker[Session]) -> None:
        self.settings = settings
        self.sessions = sessions

    async def command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """/progress: where every exercise stands, with Move up for any that are ready."""
        with session_scope(self.sessions) as session:
            standings = progress.overview(session)
        if update.effective_message is not None:
            await update.effective_message.reply_text(
                progress_text(standings), reply_markup=keyboard(standings)
            )

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """Move up / Not yet. Strangers get nothing, not even an answer (T1)."""
        query = update.callback_query
        user = update.effective_user
        if query is None or user is None or user.id != self.settings.telegram_allowed_user_id:
            return
        press = parse(query.data)
        await query.answer()
        if press is None or not isinstance(query.message, Message):
            return
        with session_scope(self.sessions) as session:
            if press.action == "up":
                text = reply(progress.move_up(session, press.exercise_id, press.step_id))
            else:
                staying = progress.not_yet(session, press.exercise_id, press.step_id)
                text = (
                    f"Staying on {staying}. I'll ask again after your next session at the top "
                    "of the range."
                    if staying is not None
                    else reply(None)
                )
        await edit_quietly(
            query.edit_message_reply_markup(_without(query.message.reply_markup, press))
        )
        await query.message.reply_text(text)
