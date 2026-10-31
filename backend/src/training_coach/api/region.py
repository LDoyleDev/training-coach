"""The EU and EEA only, in the app (ADR-0085 layer 2; threat-model.md).

Cloudflare names the visitor's country in ``CF-IPCountry``. Like ``CF-Connecting-IP`` it is
believed only from ``TC_TRUSTED_PROXIES`` (the tunnel's side), since anyone reaching the app
another way could write it. A browser route from a country outside the list gets 451: a plain
page, or for the web app's API calls JSON it shows as that page. The paths an AI app's servers
call (from the US, ADR-0054) and the health check are exempt; their own checks guard them.

No country from a trusted proxy (local development, tests, a process on the Pi, a missing
Cloudflare header) is let through, so the owner can't be locked out by a header that never came.
"""

from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from training_coach.api.passkeys import _trusted_peer
from training_coach.domain.region import admits

log = structlog.get_logger(__name__)

HEADER = "cf-ipcountry"
UNAVAILABLE = "Not available in your region"
# Called by machines, not browsers: an AI app's servers, and the Pi's own checks.
EXEMPT = frozenset({"/mcp", "/oauth/token", "/oauth/register", "/healthz"})
EXEMPT_PREFIX = "/.well-known/oauth-"
NO_STORE = {"Cache-Control": "no-store"}
PAGE = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{UNAVAILABLE}</title></head>
<body><h1>{UNAVAILABLE}</h1>
<p>Training Coach is only for people in the EU and EEA.</p></body></html>
"""


def exempt(path: str) -> bool:
    return path in EXEMPT or path.startswith(EXEMPT_PREFIX)


def visitor_country(request: Request) -> str | None:
    """The visitor's country code from a trusted proxy, or None when there is none to believe."""
    country = request.headers.get(HEADER, "").strip().upper()
    peer = request.client.host if request.client is not None else ""
    if not country or not _trusted_peer(request, peer):
        return None
    return country


async def region_guard(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    path = request.url.path
    if exempt(path):
        return await call_next(request)
    country = visitor_country(request)
    if admits(country):
        return await call_next(request)
    log.info("region.refused", country=country)
    if path.startswith("/api/"):
        return JSONResponse({"detail": UNAVAILABLE}, status_code=451, headers=NO_STORE)
    return HTMLResponse(PAGE, status_code=451, headers=NO_STORE)
