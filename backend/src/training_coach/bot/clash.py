"""The question in Telegram when a log would land on a day that already has its session
(ADR-0060): what is there, then Replace it, Move it to another day, Add to that day or Cancel.
A move offers the last week's days as buttons (a typed log also takes a typed date).

Callback data is ``<prefix>:<answer>:<ref>``, where ``<answer>`` is ``replace``, ``add``,
``move`` (show the days), ``m<n>`` (move to n days ago) or ``cancel``, and ``<ref>`` is the
caller's: a draft's token, a band workout's id, a proposal's token. The caller keeps the clash
it showed, so the answer names exactly the workouts the person saw.
"""

import re
from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from training_coach.domain.dates import date_line
from training_coach.services.day_clash import ADD, MOVE, REPLACE, Clash, Resolution

ANSWERS = frozenset({REPLACE, ADD, MOVE, "cancel"})
MOVE_TO = re.compile(r"^m(\d{1,2})$")
DAYS_SHOWN = 7
MOVE_ASK = "Move it to which day? Tap one, or send a date like Tue 6 Oct."
MOVE_ASK_BUTTONS = "Move it to which day?"
CHANGED = "That day changed since I asked. Here it is now."
CANCELLED = "Nothing was saved."


def is_answer(action: str) -> bool:
    return action in ANSWERS or MOVE_TO.match(action) is not None


def _day(on: date) -> str:
    return f"{on:%a %d %b}"


def _what(clash: Clash) -> str:
    return " and ".join(f"{r.name} ({r.summary})" for r in clash.recorded)


def text(clash: Clash) -> str:
    """Plain text: what is there, and the choices."""
    one = len(clash.recorded) == 1
    it = "it" if one else "them"
    return (
        f"{_day(clash.day)} already has {_what(clash)}.\n\n"
        f"Replace {it} with this log, move {it} to another day, or add this log to that day? "
        "Nothing is saved until you choose."
    )


def taken_text(taken: Clash) -> str:
    return f"{_day(taken.day)} has {_what(taken)} too. Pick another day."


def keyboard(prefix: str, ref: str, one: bool = True) -> InlineKeyboardMarkup:
    it = "it" if one else "them"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"Replace {it}", callback_data=f"{prefix}:{REPLACE}:{ref}"),
                InlineKeyboardButton(f"Move {it}", callback_data=f"{prefix}:{MOVE}:{ref}"),
            ],
            [
                InlineKeyboardButton("Add to that day", callback_data=f"{prefix}:{ADD}:{ref}"),
                InlineKeyboardButton("Cancel", callback_data=f"{prefix}:cancel:{ref}"),
            ],
        ]
    )


def days_keyboard(
    prefix: str, ref: str, clash: Clash, today: date, taken: date | None = None
) -> InlineKeyboardMarkup:
    """The last week's days, without the clash's day (or one already found taken)."""
    days = [n for n in range(DAYS_SHOWN) if today - timedelta(days=n) not in (clash.day, taken)]
    buttons = [
        InlineKeyboardButton(
            "Today" if n == 0 else _day(today - timedelta(days=n)),
            callback_data=f"{prefix}:m{n}:{ref}",
        )
        for n in days
    ]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    rows.append([InlineKeyboardButton("Cancel", callback_data=f"{prefix}:cancel:{ref}")])
    return InlineKeyboardMarkup(rows)


def resolution(action: str, clash: Clash, today: date) -> Resolution | None:
    """The answer a button gives, naming the workouts shown; None for Move (pick a day first)
    and Cancel."""
    seen = clash.ids
    if action in (REPLACE, ADD):
        return Resolution(action, seen)
    found = MOVE_TO.match(action)
    if found is None:
        return None
    return Resolution(MOVE, seen, today - timedelta(days=int(found[1])))


def typed_move(line: str, clash: Clash, today: date) -> Resolution | str | None:
    """A date typed after Move: the answer, a problem with the date, or None when the message
    isn't a date at all (it's a new log)."""
    dated = date_line(line.strip(), today)
    if dated is None or (not isinstance(dated, str) and dated.rest):
        return None
    if isinstance(dated, str):
        return dated
    return Resolution(MOVE, clash.ids, dated.day)
