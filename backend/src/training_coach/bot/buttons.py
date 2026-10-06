"""Inline keyboards for the morning message. Callback data is ``q:<action>:<template id>``
(plus ``:<picked id>`` for a pick); every action re-checks the id against the queue, so a
button on an old message can't act on a different session (ADR-0022)."""

from collections.abc import Awaitable
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

PREFIX = "q"
MAX_ID = 2**63
ACTIONS = frozenset({"start", "rest", "swap", "next", "pickmenu", "pick", "push", "back"})


@dataclass(frozen=True)
class Press:
    action: str
    template_id: int
    picked_id: int | None = None


def _data(action: str, template_id: int, picked_id: int | None = None) -> str:
    parts = [PREFIX, action, str(template_id)]
    if picked_id is not None:
        parts.append(str(picked_id))
    return ":".join(parts)


def parse(data: str | None) -> Press | None:
    """The button pressed, or None for anything malformed."""
    parts = (data or "").split(":")
    if len(parts) not in (3, 4) or parts[0] != PREFIX or parts[1] not in ACTIONS:
        return None
    try:
        numbers = [int(p) for p in parts[2:]]
    except ValueError:
        return None
    if not all(0 < n < MAX_ID for n in numbers):  # ids are SQLite integers; reject forgeries
        return None
    return Press(parts[1], numbers[0], numbers[1] if len(numbers) == 2 else None)


def morning(template_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Start", callback_data=_data("start", template_id)),
                InlineKeyboardButton("Rest today", callback_data=_data("rest", template_id)),
                InlineKeyboardButton("Swap", callback_data=_data("swap", template_id)),
            ]
        ]
    )


def swap(template_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Do the next one first", callback_data=_data("next", template_id)
                )
            ],
            [
                InlineKeyboardButton(
                    "Pick another session", callback_data=_data("pickmenu", template_id)
                )
            ],
            [InlineKeyboardButton("Push to tomorrow", callback_data=_data("push", template_id))],
            [InlineKeyboardButton("Back", callback_data=_data("back", template_id))],
        ]
    )


def pick(template_id: int, choices: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(name, callback_data=_data("pick", template_id, choice))]
        for choice, name in choices
        if choice != template_id
    ]
    rows.append([InlineKeyboardButton("Back", callback_data=_data("back", template_id))])
    return InlineKeyboardMarkup(rows)


async def edit_quietly(edit: Awaitable[object]) -> None:
    """Run a message edit, ignoring Telegram's refusal when nothing would change.

    Telegram answers 400 "message is not modified" when, say, a second tap retires buttons
    that are already gone. That isn't a failure, and it must not reach the error handler
    (which would tell the owner something went wrong after it worked). Other errors raise.
    """
    try:
        await edit
    except BadRequest as exc:
        if "not modified" not in str(exc).lower():
            raise
