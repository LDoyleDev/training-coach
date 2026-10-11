"""``/mcp``: the MCP endpoint a connected AI app calls (ADR-0047 C1, mcp-threat-model.md).

Every call needs ``connection``: a bearer token in the ``Authorization`` header, for this
resource, from a live connection. Without one the answer is 401 naming the protected-resource
metadata, which is how the AI app finds where to connect. Session cookies count for nothing
here, a token in the query string is refused, and a browser page from another site (``Origin``)
is refused outright (DNS rebinding). GET has no event stream to offer, so only POST is routed.
"""

import json
import time
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from training_coach.api.oauth import MCP_PATH, NO_STORE, limited, server
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
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


@router.post(
    MCP_PATH,
    response_model=None,
    responses={200: {"description": "A JSON-RPC answer"}, 202: {}, 401: {}, 403: {}},
)
async def mcp(request: Request, access: Connection) -> Response:
    """One JSON-RPC message (MCP Streamable HTTP, stateless, JSON answers)."""
    version = request.headers.get("mcp-protocol-version")
    if version is not None and version not in mcp_server.VERSIONS:
        return JSONResponse({"detail": "unsupported MCP-Protocol-Version"}, 400, NO_STORE)
    try:
        message = json.loads(await request.body())
    except (ValueError, RecursionError):  # deep nesting fits under the body cap
        return JSONResponse(mcp_server.parse_error(), 400, NO_STORE)
    settings: Settings = request.app.state.settings
    today = local_date(datetime.now(UTC), settings.tz)
    bound = make_session_factory(request.app.state.engine, user_id=access.user_id)

    def answer() -> dict[str, object] | mcp_server.NeedsScope | None:
        with session_scope(bound) as session:  # ADR-0029: only this person's rows
            return mcp_server.handle(session, access, message, today)

    result = await run_in_threadpool(answer)  # the summary's queries mustn't block the loop
    if result is None:
        return Response(status_code=status.HTTP_202_ACCEPTED, headers=NO_STORE)
    if isinstance(result, mcp_server.NeedsScope):
        challenge = _challenge(request, "insufficient_scope")
        challenge["WWW-Authenticate"] += f', scope="{result.scope}"'
        return JSONResponse({"detail": "insufficient_scope"}, 403, challenge)
    return JSONResponse(result, headers=NO_STORE)
