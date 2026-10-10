"""Passkey routes (ADR-0036): add one while signed in, sign in with one.

Each ceremony is two calls: options (which also sets a short-lived, HttpOnly cookie naming the
challenge) and the browser's answer. Options are WebAuthn JSON, handed straight to the
browser's `navigator.credentials` (via @simplewebauthn/browser).
"""

from datetime import UTC, datetime
from ipaddress import ip_address, ip_network
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.alerts import alert, device
from training_coach.api.auth import COOKIE, Fresh, Owner, set_session_cookie
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import passkeys

CHALLENGE_COOKIE = "tc_passkey"
CHALLENGE_PATH = "/api/auth/passkeys"
log = structlog.get_logger(__name__)
router = APIRouter(prefix=CHALLENGE_PATH, tags=["auth"])


class Answer(BaseModel):
    """The browser's answer to a ceremony: WebAuthn JSON, checked by the library."""

    credential: dict[str, Any] = Field(max_length=20)


def _party(request: Request) -> passkeys.Party:
    """The relying party, or 503 when TC_PUBLIC_URL is missing or unusable."""
    settings: Settings = request.app.state.settings
    if settings.public_url is not None:
        try:
            return passkeys.Party.from_url(settings.public_url)
        except ValueError:
            pass
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "sign-in isn't set up")


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _shared(request: Request) -> sessionmaker[Session]:
    sessions: sessionmaker[Session] = request.app.state.shared_sessions
    return sessions


def _options(ceremony: passkeys.Ceremony) -> Response:
    response = Response(ceremony.options, media_type="application/json")
    response.set_cookie(
        CHALLENGE_COOKIE,
        ceremony.handle,
        max_age=int(passkeys.CHALLENGE_TTL.total_seconds()),
        httponly=True,
        secure=True,
        samesite="strict",
        path=CHALLENGE_PATH,
    )
    return response


def _trusted_peer(request: Request, host: str) -> bool:
    """Whether the connection comes from the tunnel's side (TC_TRUSTED_PROXIES: loopback and
    Docker's bridge by default). Anyone else is the client itself."""
    try:
        address = ip_address(host)
    except ValueError:
        return False
    settings: Settings = request.app.state.settings
    return any(address in ip_network(cidr) for cidr in settings.trusted_proxies)


def _client(request: Request) -> str:
    """The caller's address. Behind the Cloudflare tunnel, CF-Connecting-IP names the real
    client; it is believed only from a trusted peer, so a caller reaching the app another way
    can't invent a new address per request (review of #123)."""
    peer = request.client.host if request.client is not None else "unknown"
    forwarded = request.headers.get("cf-connecting-ip")
    if forwarded and _trusted_peer(request, peer):
        return forwarded
    return peer


def _cleared() -> dict[str, str]:
    """A Set-Cookie header removing the challenge cookie, for error responses too (FastAPI
    builds a fresh response for an HTTPException, dropping cookies set on the original)."""
    response = Response()
    response.delete_cookie(CHALLENGE_COOKIE, path=CHALLENGE_PATH, secure=True, httponly=True)
    return {"set-cookie": response.headers["set-cookie"]}


def _handle(request: Request) -> str:
    handle = request.cookies.get(CHALLENGE_COOKIE)
    if not handle:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "start again")
    return handle


@router.post("/register/options")
def registration_options(request: Request, user: Owner, _fresh: Fresh) -> Response:
    """Options for adding a passkey to the signed-in person."""
    party = _party(request)
    with session_scope(_bound(request, user)) as session:
        ceremony = passkeys.registration(session, party, datetime.now(UTC))
    return _options(ceremony)


@router.post("/register", status_code=status.HTTP_204_NO_CONTENT)
def register(
    answer: Answer,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    user: Owner,
    _fresh: Fresh,
) -> None:
    party, handle = _party(request), _handle(request)
    name = request.headers.get("user-agent", "")
    with session_scope(_bound(request, user)) as session:
        added = passkeys.register(
            session, party, handle, answer.credential, name, datetime.now(UTC)
        )
    if not added:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "that passkey couldn't be added", headers=_cleared()
        )
    response.headers.update(_cleared())
    alert(
        request,
        background,
        "passkey_added",
        f"A passkey was added to Training Coach on {device(request)}. Not you? Remove it on "
        "the Account page, or send /recover.",
    )


@router.post("/sign-in/options")
def sign_in_options(request: Request) -> Response:
    """Options for signing in with a passkey; anyone may ask, only a registered key passes."""
    party = _party(request)
    try:
        with session_scope(_shared(request)) as session:
            ceremony = passkeys.sign_in_options(session, party, datetime.now(UTC), _client(request))
    except passkeys.TooManySignInsError:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "try again in a few minutes"
        ) from None
    return _options(ceremony)


@router.post("/sign-in", status_code=status.HTTP_204_NO_CONTENT)
def sign_in(
    answer: Answer, request: Request, response: Response, background: BackgroundTasks
) -> None:
    party, handle = _party(request), _handle(request)
    label = request.headers.get("user-agent", "")
    with session_scope(_shared(request)) as session:
        cookie = passkeys.sign_in(
            session, party, handle, answer.credential, datetime.now(UTC), label
        )
    if cookie is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "that passkey wasn't accepted", headers=_cleared()
        )
    response.headers.update(_cleared())
    set_session_cookie(response, cookie)
    alert(
        request,
        background,
        "passkey_sign_in",
        f"New sign-in to Training Coach with your passkey, on {device(request)}.",
    )


@router.post("/confirm/options")
def confirm_options(request: Request, user: Owner) -> Response:
    """Options to confirm it's still you with your fingerprint (ADR-0049); 409 without a
    passkey (then only signing in again with a link makes the session fresh)."""
    party = _party(request)
    with session_scope(_bound(request, user)) as session:
        ceremony = passkeys.confirmation(session, party, datetime.now(UTC))
    if ceremony is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no passkey to confirm with")
    return _options(ceremony)


@router.post("/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm(answer: Answer, request: Request, response: Response, user: Owner) -> None:
    """Confirm it's you: this browser's session counts as a fresh sign-in for 10 minutes, so
    a change that needs one goes through without signing out and in again."""
    party, handle = _party(request), _handle(request)
    token = request.cookies.get(COOKIE, "")
    with session_scope(_bound(request, user)) as session:
        confirmed = passkeys.confirm(
            session, party, handle, answer.credential, datetime.now(UTC), token
        )
    if not confirmed:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "that passkey wasn't accepted", headers=_cleared()
        )
    response.headers.update(_cleared())
    log.info("auth.confirmed")
