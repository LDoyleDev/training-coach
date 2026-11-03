"""The "ready to progress" prompt: Move up / Not yet (step 1-G; ADR-0016, ADR-0025), and the
step down suggested when the bottom of the range is out of reach: Step down / Not yet (ADR-0084).

Buttons carry ``p:<up|no|dn|nd>:<exercise id>:<step id>``: up and no answer Move up, dn and nd
a step down. The service checks everything again on a press, so a stale or forged press can at
most get an "already moved" answer.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.bot import links
from training_coach.bot.buttons import edit_quietly, row_id
from training_coach.bot.messages import progress_text, review_text
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.blocks import BlockKind
from training_coach.domain.progression import Progress
from training_coach.domain.queue import local_date
from training_coach.services import blocks, progress
from training_coach.services import review as reviews
from training_coach.services.progress import Feedback, MoveOutcome, Standing

PREFIX = "p"
STRENGTH_BLOCK_WAIT = "{exercise} waits for the hypertrophy block: this is a strength block."
MAX_ROWS = 40  # two buttons each, well under Telegram's 100
ACTIONS = {"up", "no", "dn", "nd"}


@dataclass(frozen=True)
class Press:
    action: str  # "up" or "no" (Move up), "dn" or "nd" (a step down)
    exercise_id: int
    step_id: int


def parse(data: str | None) -> Press | None:
    parts = (data or "").split(":")
    if len(parts) != 4 or parts[0] != PREFIX or parts[1] not in ACTIONS:
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


def _down_row(item: Feedback | Standing) -> list[InlineKeyboardButton]:
    """Step down / Not yet; at a ladder's first step only Not yet, as there is nothing below."""
    ids = f"{item.exercise_id}:{item.step_id}"
    no = InlineKeyboardButton("Not yet", callback_data=f"{PREFIX}:nd:{ids}")
    if item.down is None or item.down.below is None:
        return [no]
    return [
        InlineKeyboardButton(f"Step down: {item.exercise}", callback_data=f"{PREFIX}:dn:{ids}"),
        no,
    ]


def keyboard(
    items: Sequence[Feedback | Standing], *, moving_up: bool = True
) -> InlineKeyboardMarkup | None:
    """Move up / Not yet per ready exercise (none with ``moving_up`` off, in a strength block),
    and Step down / Not yet per exercise with a step down suggested. Telegram rejects a message
    with more than 100 buttons, which would lose the whole reply, so at most ``MAX_ROWS``
    prompts get them."""
    rows = []
    for item in items:
        if moving_up and item.status is Progress.READY:
            rows.append(_row(item))
        if item.down is not None:
            rows.append(_down_row(item))
    rows = rows[:MAX_ROWS]
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
        return f"{name} is on the last step in your plan, or the last one open to you."
    if outcome.outcome is MoveOutcome.STRENGTH_BLOCK:
        return STRENGTH_BLOCK_WAIT.format(exercise=name)
    if outcome.outcome is MoveOutcome.STEPPED_DOWN:
        warning = f" {outcome.warning}" if outcome.warning else ""
        return (
            f"Stepped down: {name} is now {outcome.step}. Targets for it start fresh from its "
            f"own history.{warning}"
        )
    if outcome.outcome is MoveOutcome.NO_STEP_BELOW:
        return f"{name} has no step below {outcome.step}."
    if outcome.outcome is MoveOutcome.STAYED_DOWN:
        return (
            f"Staying on {name} ({outcome.step}). I'll ask again if the bottom of the range is "
            "out of reach in a later session."
        )
    return f"{name} doesn't meet the rule any more. Keep going."


class ProgressHandlers:
    def __init__(self, settings: Settings, sessions: sessionmaker[Session]) -> None:
        self.settings = settings
        self.sessions = sessions

    async def command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """/progress: where every exercise stands, with Move up for any that are ready (not
        during a strength block, ADR-0028)."""
        with session_scope(self.sessions) as session:
            standings = progress.overview(session)
            strength = self._in_strength_block(session)
        if update.effective_message is not None:
            text = progress_text(standings)
            if strength and any(s.status is Progress.READY for s in standings):
                text += "\n\n" + STRENGTH_BLOCK_WAIT.format(exercise="Moving up")
            # A step down is the person's choice, so a strength block doesn't hold it.
            await update.effective_message.reply_text(
                text, reply_markup=keyboard(standings, moving_up=not strength)
            )

    def _in_strength_block(self, session: Session) -> bool:
        today = local_date(datetime.now(UTC), self.settings.tz)
        block = blocks.current(session, today, self.settings.tz)
        return block is not None and block.kind is BlockKind.STRENGTH

    async def review(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """/review: this week so far (Monday to today), as in Sunday's review."""
        today = local_date(datetime.now(UTC), self.settings.tz)
        with session_scope(self.sessions) as session:
            text = review_text(reviews.weekly(session, today, self.settings.tz))
        if update.effective_message is not None:
            markup = links.with_open(None, self.settings.public_url, links.REVIEW)
            await update.effective_message.reply_text(text, reply_markup=markup)

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
                text = reply(
                    progress.move_up(
                        session,
                        press.exercise_id,
                        press.step_id,
                        strength_block=self._in_strength_block(session),
                    )
                )
            elif press.action == "dn":
                text = reply(progress.step_down(session, press.exercise_id, press.step_id))
            elif press.action == "nd":
                text = reply(progress.not_yet_down(session, press.exercise_id, press.step_id))
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
