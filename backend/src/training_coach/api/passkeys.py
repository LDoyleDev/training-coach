"""Passkey routes (ADR-0036): add one while signed in, sign in with one.

Each ceremony is two calls: options (which also sets a short-lived, HttpOnly cookie naming the
challenge) and the browser's answer. Options are WebAuthn JSON, handed straight to the
browser's `navigator.credentials` (via @simplewebauthn/browser).
"""

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner, set_session_cookie
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import passkeys

CHALLENGE_COOKIE = "tc_passkey"
CHALLENGE_PATH = "/api/auth/passkeys"
router = APIRouter(prefix=CHALLENGE_PATH, tags=["auth"])


class Answer(BaseModel):
    """The browser's answer to a ceremony: WebAuthn JSON, checked by the library."""

    credential: dict[str, Any] = Field(max_length=20)


def _party(request: Request) -> passkeys.Party:
    settings: Settings = request.app.state.settings
    if settings.public_url is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "sign-in isn't set up")
    return passkeys.Party.from_url(settings.public_url)


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


def _client(request: Request) -> str:
    """The caller's address. The app listens on the Pi only (127.0.0.1), so every request
    comes through the Cloudflare tunnel, which sets CF-Connecting-IP to the real client."""
    forwarded = request.headers.get("cf-connecting-ip")
    if forwarded:
        return forwarded
    return request.client.host if request.client is not None else "unknown"


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
def registration_options(request: Request, user: Owner) -> Response:
    """Options for adding a passkey to the signed-in person."""
    party = _party(request)
    with session_scope(_bound(request, user)) as session:
        ceremony = passkeys.registration(session, party, datetime.now(UTC))
    return _options(ceremony)


@router.post("/register", status_code=status.HTTP_204_NO_CONTENT)
def register(answer: Answer, request: Request, response: Response, user: Owner) -> None:
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
def sign_in(answer: Answer, request: Request, response: Response) -> None:
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
