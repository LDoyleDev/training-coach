"""The EU and EEA only, in the app (ADR-0085 layer 2; threat-model.md).

Cloudflare names the visitor's country in ``CF-IPCountry``. Like ``CF-Connecting-IP`` it is
believed only from ``TC_TRUSTED_PROXIES`` (the tunnel's side), since anyone reaching the app
another way could write it. A browser route from a country outside the list gets 451: a plain
page, or for the web app's API calls JSON it shows as that page. The paths an AI app's servers
call (from the US, ADR-0054) and the health check are exempt; their own checks guard them.

No country from a trusted proxy (local development, tests, a process on the Pi, a missing
Cloudflare header) is let through, so the owner can't be locked out by a header that never came.
"""

import re
from collections.abc import Awaitable, Callable
from ipaddress import ip_address, ip_network

import structlog
from fastapi import Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from training_coach.config import Settings
from training_coach.domain.region import admits

log = structlog.get_logger(__name__)

HEADER = "cf-ipcountry"
UNAVAILABLE = "Not available in your region"
# Called by machines, not browsers: an AI app's servers, the band reader on the person's phone
# (its own secret guards it, ADR-0055; owner's decision, 1 Nov 2026) and the Pi's own checks.
# Exact paths only: a prefix would let "/.well-known/oauth-x/../../assets/" reach the static
# files.
EXEMPT = frozenset(
    {
        "/mcp",
        "/oauth/token",
        "/oauth/register",
        "/.well-known/oauth-protected-resource",
        "/.well-known/oauth-protected-resource/mcp",
        "/.well-known/oauth-authorization-server",
        "/api/ingest/health-connect",
        "/healthz",
    }
)
CODE = re.compile(r"[A-Z0-9]{2}")
NO_STORE = {"Cache-Control": "no-store"}
ONLY_HERE = "Training Coach is only for people in the EU and EEA."
# XX (no data) and T1 (Tor): say why, rather than leave the person guessing (ADR-0085).
UNKNOWN = frozenset({"XX", "T1"})
CANT_TELL = "We can't tell where you are, for example behind Tor or some VPNs."


def reason(country: str) -> str:
    return f"{CANT_TELL} {ONLY_HERE}" if country in UNKNOWN else ONLY_HERE


def _page(why: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{UNAVAILABLE}</title></head>
<body><h1>{UNAVAILABLE}</h1>
<p>{why}</p></body></html>
"""


def exempt(path: str) -> bool:
    return path in EXEMPT


def trusted_peer(request: Request, host: str) -> bool:
    """Whether the connection comes from the tunnel's side (TC_TRUSTED_PROXIES: loopback and
    Docker's bridge by default). Anyone else is the client itself."""
    try:
        address = ip_address(host)
    except ValueError:
        return False
    settings: Settings = request.app.state.settings
    return any(address in ip_network(cidr) for cidr in settings.trusted_proxies)


def visitor_country(request: Request) -> str | None:
    """The visitor's country code from a trusted proxy, or None when there is none to believe."""
    country = request.headers.get(HEADER, "").strip().upper()
    peer = request.client.host if request.client is not None else ""
    if not country or not trusted_peer(request, peer):
        return None
    return country if CODE.fullmatch(country) else "XX"  # not a code: as if unknown


async def region_guard(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    path = request.url.path
    if exempt(path):
        return await call_next(request)
    country = visitor_country(request)
    if country is None or admits(country):
        return await call_next(request)
    log.info("region.refused", country=country)
    why = reason(country)
    if path.startswith("/api/"):
        body = {"detail": UNAVAILABLE, "reason": why}
        return JSONResponse(body, status_code=451, headers=NO_STORE)
    return HTMLResponse(_page(why), status_code=451, headers=NO_STORE)
