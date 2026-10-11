"""The "Open in app" buttons: links from the bot's messages to the web app (C1).

The one way to build a web-app link for a button. Telegram rejects a message whose URL button
points at localhost or an IP ("Wrong HTTP URL"), which would lose the whole message, so a
button is added only for an https ``TC_PUBLIC_URL``; ``Settings`` allows plain http only for
localhost in development.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

LABEL = "Open in app"
HOME = "/"
SESSION = "/session"
PROGRESS = "/progress"
TESTS = "/tests"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "[::1]"})


def app_url(public_url: str | None, path: str) -> str | None:
    """``path`` in the web app, or None when there is no https address to link to."""
    # Settings normalises the origin (lower-case scheme, no path), so prefix checks are exact.
    if public_url is None or not public_url.startswith("https://"):
        return None
    netloc = public_url.removeprefix("https://")
    host = netloc if netloc.endswith("]") else netloc.rsplit(":", 1)[0]  # drop any port
    if host.lower() in LOCAL_HOSTS:  # Telegram refuses these even over https
        return None
    return f"{public_url}{path}"


def with_open(
    markup: InlineKeyboardMarkup | None, public_url: str | None, path: str
) -> InlineKeyboardMarkup | None:
    """``markup`` with an "Open in app" row added at the end; its other buttons stay.

    The button has no callback data, so code that swaps a message's own rows by prefix
    (``buttons.merged``, the progress prompt) leaves it in place."""
    url = app_url(public_url, path)
    if url is None:
        return markup
    rows = [list(row) for row in markup.inline_keyboard] if markup is not None else []
    rows.append([InlineKeyboardButton(LABEL, url=url)])
    return InlineKeyboardMarkup(rows)
