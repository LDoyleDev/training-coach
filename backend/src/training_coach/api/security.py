"""Security headers applied to every response (see docs/security/threat-model.md)."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    ),
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


async def security_headers_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    for header, value in SECURITY_HEADERS.items():
        response.headers.setdefault(header, value)
    return response


UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})
MAX_BODY = 64 * 1024  # every JSON body is far smaller; photos have their own limit
LARGE_BODIES = ("/api/photos/",)
CACHEABLE = ("/api/plan",)  # the public plan; everything else under /api is personal


def request_guard(
    public_url: str | None,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    """Checks on every request before it reaches a route (security review, 2026-10-10):

    - A change (POST, PUT, PATCH, DELETE) must come from the app's own pages. A browser names
      where a request comes from (``Origin``, ``Sec-Fetch-Site``); one from another site, even a
      sibling on the same domain that SameSite cookies treat as the same site, is refused.
      Requests that name no origin aren't from a browser page and carry no ambient cookie risk.
    - Bodies are refused before they're read when they declare more than ``MAX_BODY`` (photos
      excepted), and a change must declare its length.
    - Personal API answers are never stored by the browser or a cache.
    """

    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Without a public URL there is nothing to compare with, and no sign-in either.
        if request.method in UNSAFE and public_url is not None:
            origin = request.headers.get("origin")
            site = request.headers.get("sec-fetch-site")
            if origin is not None and origin != public_url:
                return JSONResponse({"detail": "cross-site request refused"}, status_code=403)
            if origin is None and site is not None and site not in ("same-origin", "none"):
                return JSONResponse({"detail": "cross-site request refused"}, status_code=403)
        if request.method in UNSAFE and not request.url.path.startswith(LARGE_BODIES):
            length = request.headers.get("content-length")
            if length is None and request.headers.get("transfer-encoding"):
                return JSONResponse({"detail": "length required"}, status_code=411)
            if length is not None and (not length.isdigit() or int(length) > MAX_BODY):
                return JSONResponse({"detail": "request too large"}, status_code=413)
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/api/") and not path.startswith(CACHEABLE):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    return guard
