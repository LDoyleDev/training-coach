"""``/mcp``: the MCP endpoint a connected AI app calls (ADR-0047 C1, mcp-threat-model.md).

Every call needs ``connection``: a bearer token in the ``Authorization`` header, for this
resource, from a live connection. Without one the answer is 401 naming the protected-resource
metadata, which is how the AI app finds where to connect. Session cookies count for nothing
here, a token in the query string is refused, and a browser page from another site (``Origin``)
is refused outright (DNS rebinding). GET has no event stream to offer, so only POST is routed.
"""

import json
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from training_coach.api.oauth import MCP_PATH, NO_STORE, limited, server
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.rate_limit import RateLimit
from training_coach.services import mcp_server, mcp_tokens
from training_coach.services.mcp_tokens import Access

router = APIRouter(tags=["mcp"])
PER_CONNECTION = 60  # requests a minute (requirement 16)
TOKEN_NAMES = frozenset({"access_token", "token", "bearer"})


def _challenge(request: Request, error: str | None = None) -> dict[str, str]:
    metadata = f"{server(request).issuer}/.well-known/oauth-protected-resource{MCP_PATH}"
    value = f'Bearer resource_metadata="{metadata}"'
    if error:
        value += f', error="{error}"'
    return {"WWW-Authenticate": value, **NO_STORE}


def connection(request: Request) -> Access:
    """The connection behind the bearer token; 401 (with the metadata pointer) without a live
    one, 403 for a browser page from another site, 429 past 60 requests a minute."""
    where = server(request)
    settings: Settings = request.app.state.settings
    origin = request.headers.get("origin")
    if origin is not None and origin != settings.public_url:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-site request refused")
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    in_query = TOKEN_NAMES & set(request.query_params)
    if scheme.lower() != "bearer" or not token or in_query:
        limited(request, "mcp")
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "connect first", headers=_challenge(request)
        )
    with session_scope(request.app.state.shared_sessions) as session:
        access = mcp_tokens.verify(session, token.strip(), where.resource, datetime.now(UTC))
    if access is None:
        limited(request, "mcp")
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "connect again",
            headers=_challenge(request, "invalid_token"),
        )
    limits: RateLimit = request.app.state.connection_limits
    key, now = str(access.connection_id), time.monotonic()
    if not limits.allow(key, now):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "too many requests",
            headers={"Retry-After": str(limits.retry_after(key, now)), **NO_STORE},
        )
    return access


Connection = Annotated[Access, Depends(connection)]
# Sends proposals waiting for the person to Telegram (bot.proposals, ADR-0058); None without
# the bot.
Announce = Callable[[], Awaitable[None]]


@router.post(
    MCP_PATH,
    response_model=None,
    responses={200: {"description": "A JSON-RPC answer"}, 202: {}, 401: {}, 403: {}},
)
async def mcp(request: Request, access: Connection, background: BackgroundTasks) -> Response:
    """One JSON-RPC message (MCP Streamable HTTP, stateless, JSON answers)."""
    version = request.headers.get("mcp-protocol-version")
    if version is not None and version not in mcp_server.VERSIONS:
        return JSONResponse({"detail": "unsupported MCP-Protocol-Version"}, 400, NO_STORE)
    try:
        message = json.loads(await request.body())
    except (ValueError, RecursionError):  # deep nesting fits under the body cap
        return JSONResponse(mcp_server.parse_error(), 400, NO_STORE)
    settings: Settings = request.app.state.settings
    bound = make_session_factory(request.app.state.engine, user_id=access.user_id)

    def answer() -> tuple[dict[str, object] | mcp_server.NeedsScope | None, Response | None]:
        with session_scope(bound) as session:  # ADR-0029: only this person's rows
            found = mcp_server.handle(session, access, message, settings.tz, datetime.now(UTC))
            # Encoded before the commit: an answer that can't be sent rolls back what the call
            # wrote, so an AI told it failed hasn't left a proposal waiting (eval of 2026-10-24).
            sent = JSONResponse(found, headers=NO_STORE) if isinstance(found, dict) else None
            return found, sent

    result, sent = await run_in_threadpool(answer)  # the summary's queries mustn't block the loop
    announce: Announce | None = getattr(request.app.state, "announce_proposals", None)
    if announce is not None and mcp_server.proposed(message, result):
        background.add_task(announce)  # Telegram hears of it now, not at the next check
    if isinstance(result, mcp_server.NeedsScope):
        challenge = _challenge(request, "insufficient_scope")
        challenge["WWW-Authenticate"] += f', scope="{result.scope}"'
        return JSONResponse({"detail": "insufficient_scope"}, 403, challenge)
    if sent is None:  # a notification or a response
        return Response(status_code=status.HTTP_202_ACCEPTED, headers=NO_STORE)
    return sent
