"""The "Open in app" buttons: links from the bot's messages to the web app (C1).

The one way to build a web-app link for a button. Telegram rejects a message whose URL button
points at localhost or an IP address ("Wrong HTTP URL"), which would lose the whole message, so
a button is added only for an https ``TC_PUBLIC_URL`` whose host is a domain name, not
localhost and not an IPv4 or IPv6 literal. ``Settings`` allows plain http only for localhost in
development, so that never gets a button.
"""

import ipaddress

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

LABEL = "Open in app"
HOME = "/"
SESSION = "/session"
PROGRESS = "/progress"
REVIEW = "/review"
TESTS = "/body?tab=tests"  # Tests is a tab of Body (ADR-0069)
ACCOUNT = "/account"
LOCAL_HOSTS = frozenset({"localhost"})


def _host(netloc: str) -> str:
    """The host of ``host[:port]`` or ``[ipv6][:port]``, without brackets or port."""
    if netloc.startswith("["):
        return netloc[1:].split("]", 1)[0]
    return netloc.rsplit(":", 1)[0]


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def app_url(public_url: str | None, path: str) -> str | None:
    """``path`` in the web app, or None when there is no https address to link to."""
    # Settings normalises the origin (lower-case scheme, no path), so prefix checks are exact.
    if public_url is None or not public_url.startswith("https://"):
        return None
    host = _host(public_url.removeprefix("https://"))
    if host.lower() in LOCAL_HOSTS or _is_ip(host):  # Telegram refuses these even over https
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
