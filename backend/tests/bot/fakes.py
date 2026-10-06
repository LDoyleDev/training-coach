"""A faked Telegram Bot API for driving real updates through the PTB dispatcher."""

import json
from typing import Any
from urllib.parse import parse_qs

import respx
from pydantic import SecretStr
from telegram import Update
from telegram.ext import Application

from training_coach.config import Settings

TELEGRAM = r"https://api\.telegram\.org/bot[^/]+/"
BOT_USER = {"id": 1, "is_bot": True, "first_name": "Coach", "username": "coach_bot"}
OWNER, STRANGER = 42, 99
SETTINGS = Settings(
    environment="test",
    telegram_bot_token=SecretStr("123456:TEST-TOKEN"),
    telegram_allowed_user_id=OWNER,
)
DATE = 1_790_000_000
NOT_MODIFIED = {
    "ok": False,
    "error_code": 400,
    "description": "Bad Request: message is not modified: specified new message content and "
    "reply markup are exactly the same",
}


def _message(user_id: int, text: str, message_id: int = 1) -> dict[str, Any]:
    return {
        "message_id": message_id,
        "date": DATE,
        "chat": {"id": user_id, "type": "private"},
        "from": {"id": user_id, "is_bot": False, "first_name": "Someone"},
        "text": text,
    }


def command(text: str, user_id: int) -> dict[str, Any]:
    message = _message(user_id, text)
    message["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text)}]
    return {"update_id": 1, "message": message}


def text_message(text: str, user_id: int) -> dict[str, Any]:
    """Plain text, not a command."""
    return {"update_id": 3, "message": _message(user_id, text)}


def press(data: str, user_id: int) -> dict[str, Any]:
    """A button press on a message the bot sent to ``user_id``."""
    message = _message(user_id, "Today: ...", message_id=7)
    message["from"] = BOT_USER
    return {
        "update_id": 2,
        "callback_query": {
            "id": "cb1",
            "from": {"id": user_id, "is_bot": False, "first_name": "Someone"},
            "chat_instance": "ci",
            "message": message,
            "data": data,
        },
    }


Calls = dict[str, list[dict[str, str]]]


async def run(
    application: Application,  # type: ignore[type-arg]
    update: dict[str, Any],
    *,
    unmodified: bool = False,
) -> Calls:
    """Process one update with Telegram faked; return the Bot API calls made, by method.

    ``unmodified`` answers message edits the way Telegram does when nothing would change
    (HTTP 400 "message is not modified"), e.g. retiring buttons that are already gone.
    """
    sent = {"ok": True, "result": _message(OWNER, "ok", message_id=8) | {"from": BOT_USER}}
    with respx.mock(assert_all_called=False) as telegram:
        telegram.post(url__regex=TELEGRAM + "getMe$").respond(json={"ok": True, "result": BOT_USER})
        telegram.post(url__regex=TELEGRAM + "sendMessage$").respond(json=sent)
        edited = {"status_code": 400, "json": NOT_MODIFIED} if unmodified else {"json": sent}
        telegram.post(url__regex=TELEGRAM + "editMessageReplyMarkup$").respond(**edited)
        telegram.post(url__regex=TELEGRAM + "editMessageText$").respond(**edited)
        telegram.post(url__regex=TELEGRAM + "answerCallbackQuery$").respond(
            json={"ok": True, "result": True}
        )
        await application.initialize()
        try:
            parsed = Update.de_json(update, application.bot)
            assert parsed is not None
            await application.process_update(parsed)
        finally:
            await application.shutdown()
        calls: Calls = {}  # read inside the context: respx resets its calls on exit
        for call in telegram.calls:
            method = str(call.request.url).rsplit("/", 1)[-1]
            if method != "getMe":
                form = parse_qs(call.request.content.decode())
                calls.setdefault(method, []).append({k: v[0] for k, v in form.items()})
    return calls


def texts(calls: Calls) -> list[str]:
    return [c["text"] for c in calls.get("sendMessage", [])]


def button_data(call: dict[str, str]) -> list[str]:
    """Callback data of every button in a call's reply_markup."""
    markup = json.loads(call.get("reply_markup", "null")) or {"inline_keyboard": []}
    return [b["callback_data"] for row in markup["inline_keyboard"] for b in row]
