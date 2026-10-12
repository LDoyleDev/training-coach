"""Telegram alerts about sign-ins and passkeys (ADR-0040): anything a person didn't do
themselves shows up at once, in their own chat. Sent after the response, never blocking or
failing a request; with the bot off, or for someone with no Telegram linked, there is nobody to
tell and only the log line remains."""

from collections.abc import Awaitable, Callable

import structlog
from fastapi import BackgroundTasks, Request

from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import users

log = structlog.get_logger(__name__)

Notify = Callable[[str], Awaitable[object]]
Send = Callable[[int, str], Awaitable[object]]  # a Telegram chat id, the text
DEVICE_LENGTH = 80  # the browser as it names itself; plain text in Telegram, so harmless


def device(request: Request) -> str:
    return request.headers.get("user-agent", "")[:DEVICE_LENGTH] or "an unknown browser"


def alert(request: Request, background: BackgroundTasks, user: int, kind: str, text: str) -> None:
    """Tell ``user``, the person it's about, on Telegram; ``kind`` is the log event (never the
    text, which may name a device). Ops messages go to the owner through ``state.notify``."""
    log.info("auth.alert", kind=kind)
    send: Send | None = getattr(request.app.state, "send", None)
    if send is None:
        return
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        chat = users.telegram_chat(session, user)
    if chat is not None:
        background.add_task(send, chat, text)
