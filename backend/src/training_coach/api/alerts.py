"""Telegram alerts about sign-ins and passkeys (ADR-0040): anything Liam didn't do himself shows
up at once. Sent after the response, never blocking or failing a request; with the bot off
there is nobody to tell and only the log line remains."""

from collections.abc import Awaitable, Callable

import structlog
from fastapi import BackgroundTasks, Request

log = structlog.get_logger(__name__)

Notify = Callable[[str], Awaitable[object]]
DEVICE_LENGTH = 80  # the browser as it names itself; plain text in Telegram, so harmless


def device(request: Request) -> str:
    return request.headers.get("user-agent", "")[:DEVICE_LENGTH] or "an unknown browser"


def alert(request: Request, background: BackgroundTasks, kind: str, text: str) -> None:
    """Tell the owner on Telegram; ``kind`` is the log event (never the text, which may name
    a device)."""
    log.info("auth.alert", kind=kind)
    notify: Notify | None = getattr(request.app.state, "notify", None)
    if notify is not None:
        background.add_task(notify, text)
