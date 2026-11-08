"""/undo (ADR-0048): take back the last rest day, push, swap or saved log, after a confirm tap.

Callback data is ``u:<event id>`` to undo that change, or ``u:keep``. The service checks the
id is still the last change, so a button from an older /undo can't take back a newer one.
"""

from datetime import UTC, datetime

import structlog
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.bot.buttons import edit_quietly, row_id
from training_coach.bot.gate import Person
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.services import undo

log = structlog.get_logger(__name__)

PREFIX = "u"
KEEP = "keep"
REFUSED = {
    undo.NOTHING: "Nothing to undo. I can undo the last rest day, swap, push or saved log.",
    undo.TOO_OLD: "The last change was more than a day ago, so it can't be undone.",
    undo.CHANGED: "Something changed since then (another log or button), so I can't undo it "
    "safely. Send /undo again to see what can be.",
}
KEPT = "Kept as it was."


def parse(data: str | None) -> int | None:
    """The event id a confirm button names, 0 for keep, None for anything malformed."""
    parts = (data or "").split(":")
    if len(parts) != 2 or parts[0] != PREFIX:
        return None
    return 0 if parts[1] == KEEP else row_id(parts[1])


def confirm(found: undo.Undoable) -> tuple[str, InlineKeyboardMarkup]:
    markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Undo it", callback_data=f"{PREFIX}:{found.event_id}"),
                InlineKeyboardButton("Keep it", callback_data=f"{PREFIX}:{KEEP}"),
            ]
        ]
    )
    return f"Undo {found.what}?", markup


def undone_text(done: undo.Undone) -> str:
    text = f"Undone: {done.what}."
    return f"{text} Next up: {done.next_session}." if done.next_session else text


class UndoHandlers:
    """Each handler gets the person the gate found and works in their sessions only."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def command(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person
    ) -> None:
        if update.effective_message is None:
            return
        with session_scope(me.sessions) as session:
            found = undo.last(session, datetime.now(UTC))
        if isinstance(found, undo.Blocked):
            await update.effective_message.reply_text(REFUSED[found.reason])
            return
        text, markup = confirm(found)
        await update.effective_message.reply_text(text, reply_markup=markup)

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        """A confirm button: the id names one of the presser's own changes, or nothing."""
        query = update.callback_query
        if query is None:
            return
        event_id = parse(query.data)
        if event_id is None or not isinstance(query.message, Message):
            await query.answer()
            return
        await query.answer()
        await edit_quietly(query.edit_message_reply_markup(None))
        if event_id == 0:
            await query.message.reply_text(KEPT)
            return
        with session_scope(me.sessions) as session:
            result = undo.apply(session, event_id, datetime.now(UTC))
        if isinstance(result, undo.Blocked):
            await query.message.reply_text(REFUSED[result.reason])
            log.info("bot.undo_refused", reason=result.reason)
            return
        await query.message.reply_text(undone_text(result))
        log.info("bot.undone")
