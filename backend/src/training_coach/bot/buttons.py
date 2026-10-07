"""Inline keyboards for the morning message. Callback data is ``q:<action>:<template id>``
(plus ``:<picked id>`` for a pick); every action re-checks the id against the queue, so a
button on an old message can't act on a different session (ADR-0022)."""

from collections.abc import Awaitable, Sequence
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


def row_id(text: str) -> int | None:
    """A database id from callback data: plain ASCII digits within SQLite's integer range.
    ``int()`` alone also takes " 1", "+1", "1_0" and other scripts' digits."""
    if not (text.isascii() and text.isdecimal()):
        return None
    number = int(text)
    return number if 0 < number < MAX_ID else None


def parse(data: str | None) -> Press | None:
    """The button pressed, or None for anything malformed."""
    parts = (data or "").split(":")
    if len(parts) not in (3, 4) or parts[0] != PREFIX or parts[1] not in ACTIONS:
        return None
    found = [row_id(p) for p in parts[2:]]
    numbers = [n for n in found if n is not None]
    if len(numbers) != len(found):  # ids are SQLite integers; reject forgeries
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


def _owned(row: Sequence[InlineKeyboardButton], prefix: str) -> bool:
    return all(str(b.callback_data or "").startswith(f"{prefix}:") for b in row)


def merged(
    current: InlineKeyboardMarkup | None,
    prefix: str,
    rows: Sequence[Sequence[InlineKeyboardButton]],
) -> InlineKeyboardMarkup | None:
    """``current`` with its ``prefix`` rows replaced by ``rows``, where they were (or at the end).

    One message can carry the morning buttons and the habit buttons (#91); each set changes
    only its own rows, so retiring the morning buttons leaves the habits, and the other way
    round. None when nothing is left."""
    result: list[list[InlineKeyboardButton]] = []
    placed = False
    for row in current.inline_keyboard if current is not None else ():
        if not _owned(row, prefix):
            result.append(list(row))
        elif not placed:
            result += [list(r) for r in rows]
            placed = True
    if not placed:
        result += [list(r) for r in rows]
    return InlineKeyboardMarkup(result) if result else None


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
