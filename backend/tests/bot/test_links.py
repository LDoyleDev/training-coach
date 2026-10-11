"""The "Open in app" button (C1): on the morning message, /today, the weekly review and a
saved log, only for an https TC_PUBLIC_URL, and never in place of a message's own buttons."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.orm import Session, sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application

from tests.bot.fakes import OWNER, SETTINGS, command, press, run, text_message
from training_coach.bot import buttons, links
from training_coach.bot.app import Handlers, build_bot
from training_coach.config import Settings

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]
WEB = "https://coach.example.com"
LINKED = SETTINGS.model_copy(update={"public_url": WEB})
LOCAL = SETTINGS.model_copy(update={"public_url": "http://localhost:8080"})


def _buttons(call: dict[str, str]) -> list[list[tuple[str, str]]]:
    """Each row of a sent message's buttons as (callback data or url, label)."""
    markup = json.loads(call.get("reply_markup", "null")) or {"inline_keyboard": []}
    return [
        [(b.get("callback_data") or b["url"], b["text"]) for b in row]
        for row in markup["inline_keyboard"]
    ]


def _urls(markup: InlineKeyboardMarkup | None) -> list[str]:
    rows = markup.inline_keyboard if markup is not None else ()
    return [b.url for row in rows for b in row if b.url is not None]


def _context() -> SimpleNamespace:
    return SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock(return_value=None)))


# ------------------------------------------------------------------ building the link


@pytest.mark.parametrize(
    ("public_url", "expected"),
    [
        (WEB, f"{WEB}/session"),
        (None, None),
        # Telegram refuses URL buttons for localhost ("Wrong HTTP URL"), losing the message.
        ("http://localhost:8080", None),
        ("http://127.0.0.1:8080", None),
        ("https://localhost:8443", None),
        ("https://localhost", None),
        ("https://[::1]", None),
        ("https://[::1]:8443", None),
        ("https://127.0.0.1", None),
        ("https://192.168.1.5", None),
        ("https://10.0.0.2:8443", None),
        ("https://[2001:db8::1]", None),
        ("https://[2001:db8::1]:8443", None),
        ("https://LOCALHOST", None),
        ("https://coach.example.com:8443", "https://coach.example.com:8443/session"),
    ],
)
def test_app_url_is_https_only(public_url: str | None, expected: str | None) -> None:
    assert links.app_url(public_url, links.SESSION) == expected


def test_the_settings_origin_makes_a_clean_link() -> None:
    settings = Settings(environment="test", public_url=f"{WEB}/")
    assert links.app_url(settings.public_url, links.HOME) == f"{WEB}/"


def test_with_open_appends_a_row_and_keeps_the_others() -> None:
    markup = links.with_open(buttons.morning(5), WEB, links.SESSION)
    assert markup is not None
    first, last = markup.inline_keyboard
    assert [b.callback_data for b in first] == ["q:start:5", "q:rest:5", "q:swap:5"]
    assert [(b.text, b.url) for b in last] == [("Open in app", f"{WEB}/session")]


def test_with_open_leaves_the_markup_alone_without_a_link() -> None:
    morning = buttons.morning(5)
    assert links.with_open(morning, None, links.SESSION) is morning
    assert links.with_open(None, "http://localhost:8080", links.SESSION) is None
    assert _urls(links.with_open(None, WEB, links.PROGRESS)) == [f"{WEB}/progress"]


def test_retiring_the_morning_buttons_keeps_open_in_app() -> None:
    """``buttons.merged`` swaps only its own rows, so Rest/Swap never drop the link."""
    current = links.with_open(buttons.morning(5), WEB, links.SESSION)
    assert _urls(buttons.merged(current, buttons.PREFIX, ())) == [f"{WEB}/session"]
    swapped = buttons.merged(current, buttons.PREFIX, buttons.swap(5).inline_keyboard)
    assert swapped is not None
    assert swapped.inline_keyboard[-1] == (
        InlineKeyboardButton("Open in app", url=f"{WEB}/session"),
    )


# ------------------------------------------------------------------ on the bot's messages


async def test_today_gets_open_in_app_under_its_buttons(seeded: Sessions) -> None:
    calls = await run(build_bot(LINKED, seeded), command("/today", OWNER))
    *rows, last = _buttons(calls["sendMessage"][0])
    assert [label for _, label in rows[0]] == ["Start", "Rest today", "Swap"]
    assert last == [(f"{WEB}/session", "Open in app")]


@pytest.mark.parametrize("settings", [SETTINGS, LOCAL])
async def test_today_has_no_link_without_an_https_address(
    seeded: Sessions, settings: Settings
) -> None:
    calls = await run(build_bot(settings, seeded), command("/today", OWNER))
    assert [label for _, label in _buttons(calls["sendMessage"][0])[-1]] == [
        "Start",
        "Rest today",
        "Swap",
    ]


async def test_the_morning_message_links_to_the_session(seeded: Sessions) -> None:
    context = _context()
    await Handlers(LINKED, seeded).morning(context)  # type: ignore[arg-type]  # fake context
    markup = context.bot.send_message.await_args.kwargs["reply_markup"]
    assert [b.text for b in markup.inline_keyboard[0]] == ["Start", "Rest today", "Swap"]
    assert _urls(markup) == [f"{WEB}/session"]


async def test_the_morning_message_has_no_link_without_an_address(seeded: Sessions) -> None:
    context = _context()
    await Handlers(SETTINGS, seeded).morning(context)  # type: ignore[arg-type]  # fake context
    assert _urls(context.bot.send_message.await_args.kwargs["reply_markup"]) == []


async def test_the_weekly_review_links_to_progress(seeded: Sessions) -> None:
    context = _context()
    await Handlers(LINKED, seeded).weekly_review(context)  # type: ignore[arg-type]  # fake
    assert _urls(context.bot.send_message.await_args.kwargs["reply_markup"]) == [f"{WEB}/progress"]


async def test_the_weekly_review_has_no_buttons_without_an_address(seeded: Sessions) -> None:
    context = _context()
    await Handlers(SETTINGS, seeded).weekly_review(context)  # type: ignore[arg-type]  # fake
    assert context.bot.send_message.await_args.kwargs["reply_markup"] is None


async def test_review_command_links_to_progress(seeded: Sessions) -> None:
    calls = await run(build_bot(LINKED, seeded), command("/review", OWNER))
    assert _buttons(calls["sendMessage"][0]) == [[(f"{WEB}/progress", "Open in app")]]


async def test_a_saved_log_links_home_under_its_other_buttons(seeded: Sessions) -> None:
    application = build_bot(LINKED, seeded)
    drafted = await run(application, text_message("pull ups 8 8 7, dips 12 11", OWNER))
    (draft_rows,) = _buttons(drafted["sendMessage"][0])  # Save / Edit / Cancel: no link yet
    token = draft_rows[0][0].split(":")[2]
    saved = await run(application, press(f"l:save:{token}", OWNER))
    *rows, last = _buttons(saved["sendMessage"][0])
    assert last == [(f"{WEB}/", "Open in app")]
    assert all(data.startswith(("p:", "st:")) for row in rows for data, _ in row)


async def test_no_plan_means_no_link(sessions: Sessions) -> None:
    calls = await run(build_bot(LINKED, sessions), command("/today", OWNER))
    assert _buttons(calls["sendMessage"][0]) == []
