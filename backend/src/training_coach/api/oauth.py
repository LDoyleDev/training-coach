"""The OAuth routes for "Connect my AI" (ADR-0047 C, docs/security/mcp-threat-model.md).

- Discovery: protected-resource metadata (RFC 9728) and authorization-server metadata (RFC
  8414), so an AI app finds everything from the ``/mcp`` URL alone.
- ``/oauth/register`` (RFC 7591), ``/oauth/authorize`` and ``/oauth/token``: public, as the AI
  app calls them, and limited per client address.
- ``/api/connect/*``: the consent page (``/connect`` in the web app). Approving needs a passkey
  proved on that page in the last few minutes; approval returns the app's address for the page
  to go to, so the global CSP (``form-action 'self'``) stays as it is.
"""

import html
import time
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Body, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.alerts import alert
from training_coach.api.auth import Owner, PasskeyFresh
from training_coach.api.passkeys import _client
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.connections import Scope
from training_coach.domain.rate_limit import RateLimit
from training_coach.services import mcp_tokens, oauth
from training_coach.services.mcp_tokens import Refused, Tokens

router = APIRouter(tags=["oauth"])
MCP_PATH = "/mcp"
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}
# Unauthenticated calls per client address and route, a minute (requirement 16).
PER_ADDRESS = 30


def server(request: Request) -> oauth.Server:
    """Where this server is, from TC_PUBLIC_URL; 404 without it (nothing to connect to)."""
    settings: Settings = request.app.state.settings
    if settings.public_url is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not set up")
    return oauth.Server(settings.public_url, settings.public_url + MCP_PATH)


def limited(request: Request, route: str) -> None:
    """429 when this client address has called ``route`` too often in the last minute."""
    limits: RateLimit = request.app.state.address_limits
    key = f"{route} {_client(request)}"
    now = time.monotonic()
    if not limits.allow(key, now):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "too many requests",
            headers={"Retry-After": str(limits.retry_after(key, now)), **NO_STORE},
        )


def _shared(request: Request) -> sessionmaker[Session]:
    sessions: sessionmaker[Session] = request.app.state.shared_sessions
    return sessions


# ----------------------------------------------------------------------- discovery


class ResourceMetadata(BaseModel):
    resource: str
    authorization_servers: list[str]
    scopes_supported: list[str]
    bearer_methods_supported: list[str]
    resource_name: str


class ServerMetadata(BaseModel):
    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str
    scopes_supported: list[str]
    response_types_supported: list[str]
    response_modes_supported: list[str]
    grant_types_supported: list[str]
    code_challenge_methods_supported: list[str]
    token_endpoint_auth_methods_supported: list[str]
    authorization_response_iss_parameter_supported: bool


def _resource_metadata(request: Request) -> ResourceMetadata:
    where = server(request)
    return ResourceMetadata(
        resource=where.resource,
        authorization_servers=[where.issuer],
        scopes_supported=[s.value for s in Scope],
        bearer_methods_supported=["header"],
        resource_name="Training Coach",
    )


@router.get("/.well-known/oauth-protected-resource", response_model=ResourceMetadata)
def resource_metadata(request: Request) -> ResourceMetadata:
    """RFC 9728: what ``/mcp`` is and which server issues its tokens."""
    return _resource_metadata(request)


@router.get("/.well-known/oauth-protected-resource/mcp", response_model=ResourceMetadata)
def resource_metadata_for_mcp(request: Request) -> ResourceMetadata:
    """The same, at the path RFC 9728 derives from the ``/mcp`` URL."""
    return _resource_metadata(request)


@router.get("/.well-known/oauth-authorization-server", response_model=ServerMetadata)
def server_metadata(request: Request) -> ServerMetadata:
    """RFC 8414. Public clients only (``none``), PKCE S256 only, registration open but bounded.
    No client ID metadata documents: Claude then registers (its documented fallback)."""
    issuer = server(request).issuer
    return ServerMetadata(
        issuer=issuer,
        authorization_endpoint=f"{issuer}/oauth/authorize",
        token_endpoint=f"{issuer}/oauth/token",
        registration_endpoint=f"{issuer}/oauth/register",
        scopes_supported=[s.value for s in Scope],
        response_types_supported=["code"],
        response_modes_supported=["query"],
        grant_types_supported=["authorization_code", "refresh_token"],
        code_challenge_methods_supported=["S256"],
        token_endpoint_auth_methods_supported=["none"],
        authorization_response_iss_parameter_supported=True,
    )


# -------------------------------------------------------------------- registration


@router.post(
    "/oauth/register",
    status_code=status.HTTP_201_CREATED,
    response_model=None,
    responses={201: {"description": "Registered (RFC 7591)"}, 400: {}, 429: {}},
)
def register(
    request: Request, metadata: Annotated[dict[str, Any], Body(max_length=20)]
) -> JSONResponse:
    """Dynamic client registration (RFC 7591), bounded: registering grants nothing until the
    person approves the app with their passkey."""
    server(request)
    limited(request, "register")
    with session_scope(_shared(request)) as session:
        result = oauth.register(session, metadata, _client(request), datetime.now(UTC))
    if isinstance(result, oauth.Busy):
        return JSONResponse(
            {"error": "temporarily_unavailable", "error_description": "try again shortly"},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(result.retry_after), **NO_STORE},
        )
    if isinstance(result, oauth.Invalid):
        return JSONResponse(
            {"error": result.error, "error_description": result.description},
            status_code=status.HTTP_400_BAD_REQUEST,
            headers=NO_STORE,
        )
    return JSONResponse(
        {
            "client_id": result.client_id,
            "client_id_issued_at": int(result.issued_at.timestamp()),
            "client_name": result.name,
            "redirect_uris": result.redirect_uris,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        },
        status_code=status.HTTP_201_CREATED,
        headers=NO_STORE,
    )


# ----------------------------------------------------------------------- authorize


def _error_page(message: str, status_code: int) -> HTMLResponse:
    """An error shown here: never a redirect to an address that can't be trusted."""
    body = (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Training Coach</title><h1>This app can't connect</h1>"
        f"<p>{html.escape(message)}</p><p>Nothing was shared. Go back to your AI app and try "
        'again, or <a href="/account">open your account</a>.</p>'
    )
    return HTMLResponse(body, status_code=status_code, headers=NO_STORE)


@router.get(
    "/oauth/authorize",
    response_class=Response,
    responses={303: {"description": "To the consent page"}, 302: {}, 400: {}, 429: {}},
)
def authorize(request: Request) -> Response:
    """The authorization request (OAuth 2.1, PKCE S256, RFC 8707). On to the consent page with
    a handle (in the fragment, so no log or Referer sees it), or an error."""
    where = server(request)
    limited(request, "authorize")
    params = dict(request.query_params)
    with session_scope(_shared(request)) as session:
        result = oauth.authorize(session, params, where, _client(request), datetime.now(UTC))
    if isinstance(result, oauth.ErrorPage):
        return _error_page(result.message, result.status)
    if isinstance(result, oauth.ErrorRedirect):
        return RedirectResponse(result.url, status.HTTP_302_FOUND, headers=NO_STORE)
    return RedirectResponse(f"/connect#{result}", status.HTTP_303_SEE_OTHER, headers=NO_STORE)


# --------------------------------------------------------------------------- token


def _token_error(error: str, status_code: int = status.HTTP_400_BAD_REQUEST) -> JSONResponse:
    return JSONResponse({"error": error}, status_code=status_code, headers=NO_STORE)


@router.post(
    "/oauth/token",
    response_model=None,
    responses={200: {"description": "Tokens (RFC 6749 section 5.1)"}, 400: {}, 401: {}},
)
async def token(request: Request, background: BackgroundTasks) -> JSONResponse:
    """The token endpoint, form-encoded (RFC 6749): a code for tokens, or a refresh."""
    where = server(request)
    limited(request, "token")
    if request.headers.get("content-type", "").split(";")[0].strip() != oauth.FORM:
        return _token_error("invalid_request")
    fields = oauth.form(await request.body())
    if fields is None:
        return _token_error("invalid_request")
    grant = fields.get("grant_type")
    client_id = fields.get("client_id", "")
    now = datetime.now(UTC)
    with session_scope(_shared(request)) as session:
        if oauth.find_client(session, client_id, now) is None:
            return _token_error("invalid_client", status.HTTP_401_UNAUTHORIZED)
        result: Tokens | Refused
        if grant == "authorization_code":
            required = ("code", "redirect_uri", "code_verifier")
            if not all(fields.get(name) for name in required):
                return _token_error("invalid_request")
            result = mcp_tokens.exchange_code(
                session,
                fields["code"],
                client_id,
                fields["redirect_uri"],
                fields["code_verifier"],
                fields.get("resource"),
                where.resource,
                now,
            )
        elif grant == "refresh_token":
            if not fields.get("refresh_token"):
                return _token_error("invalid_request")
            result = mcp_tokens.refresh(
                session,
                fields["refresh_token"],
                client_id,
                fields.get("scope"),
                fields.get("resource"),
                where.resource,
                now,
            )
        else:
            return _token_error("unsupported_grant_type")
    if isinstance(result, Refused):
        if result.revoked:
            alert(
                request,
                background,
                "mcp_token_reused",
                "A connected AI app's sign-in was used twice, so its connection to Training "
                "Coach was ended. If you still use it, connect it again; if not, someone may "
                "have copied it.",
            )
        return _token_error(result.error)
    return JSONResponse(
        {
            "access_token": result.access_token,
            "token_type": "Bearer",
            "expires_in": result.expires_in,
            "refresh_token": result.refresh_token,
            "scope": result.scope,
        },
        headers=NO_STORE,
    )


# --------------------------------------------------------------------- the consent page


class ConsentHandle(BaseModel):
    handle: str = Field(min_length=20, max_length=100)


class ConsentScopeView(BaseModel):
    scope: str
    label: str
    health: bool  # starts unticked


class ConsentView(BaseModel):
    client_id: str
    client_name: str
    redirect_uri: str
    redirect_host: str
    scopes: list[ConsentScopeView]


class ApproveBody(BaseModel):
    handle: str = Field(min_length=20, max_length=100)
    client_id: str = Field(max_length=64)
    redirect_uri: str = Field(max_length=200)
    scopes: list[str] = Field(max_length=len(Scope))


class GoTo(BaseModel):
    redirect: str


@router.post("/api/connect/details", response_model=ConsentView)
def consent_details(body: ConsentHandle, request: Request) -> ConsentView:
    """What a consent page asks for. Public: the handle is the secret, and nothing here is
    personal."""
    with session_scope(_shared(request)) as session:
        found = oauth.details(session, body.handle, datetime.now(UTC))
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "this request has expired")
    return ConsentView(
        client_id=found.client_id,
        client_name=found.client_name,
        redirect_uri=found.redirect_uri,
        redirect_host=found.redirect_host,
        scopes=[ConsentScopeView(**vars(s)) for s in found.scopes],
    )


@router.post("/api/connect/bind", status_code=status.HTTP_204_NO_CONTENT)
def consent_bind(body: ConsentHandle, request: Request, user: Owner, proof: PasskeyFresh) -> None:
    """Bind a consent page to this browser, once its passkey is proved on the page."""
    with session_scope(_shared(request)) as session:
        bound = oauth.bind(session, body.handle, user, proof.session_id, datetime.now(UTC))
    if not bound:
        raise HTTPException(status.HTTP_409_CONFLICT, "this request has expired")


@router.post("/api/connect/approve", response_model=GoTo)
def consent_approve(
    body: ApproveBody,
    request: Request,
    background: BackgroundTasks,
    user: Owner,
    proof: PasskeyFresh,
) -> GoTo:
    """Approve: a connection with the scopes ticked, and the app's address with its code."""
    issuer = server(request).issuer
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        result = oauth.approve(
            session,
            body.handle,
            proof.session_id,
            proof.passkey_id,
            body.client_id,
            body.redirect_uri,
            body.scopes,
            issuer,
            datetime.now(UTC),
        )
    if isinstance(result, oauth.Refusal):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, result.reason)
    alert(
        request,
        background,
        "mcp_connected",
        f'An AI app was connected to Training Coach. It calls itself "{result.client_name}" '
        f"and sends you back to {result.redirect_host}. It may read: "
        f"{', '.join(result.scopes)}. Not you? Revoke it on the Account page.",
    )
    return GoTo(redirect=result.redirect)


@router.post("/api/connect/deny", response_model=GoTo)
def consent_deny(body: ConsentHandle, request: Request) -> GoTo:
    """Don't allow: back to the app with ``access_denied``. Public, like the details."""
    issuer = server(request).issuer
    with session_scope(_shared(request)) as session:
        redirect = oauth.deny(session, body.handle, issuer, datetime.now(UTC))
    if redirect is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "this request has expired")
    return GoTo(redirect=redirect)
