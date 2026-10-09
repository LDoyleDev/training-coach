"""Sign-in routes (ADR-0036) and ``owner``, the dependency every personal route declares.

A session is a cookie: HttpOnly, Secure, SameSite=Strict, holding a random token that the
database stores only hashed. ``test_every_route_is_public_or_owner_only`` keeps each route's
access deliberate.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.db.session import session_scope
from training_coach.services import auth

COOKIE = "tc_session"
router = APIRouter(prefix="/api/auth", tags=["auth"])


class Redeem(BaseModel):
    token: str = Field(min_length=20, max_length=100)


class Me(BaseModel):
    user_id: int


def _shared(request: Request) -> sessionmaker[Session]:
    """Unbound sessions, only for finding whose token a token is (services.auth)."""
    sessions: sessionmaker[Session] = request.app.state.shared_sessions
    return sessions


def owner(request: Request, response: Response) -> int:
    """The signed-in user's id; 401 without a live session. When the session is renewed, the
    cookie is sent again so the browser keeps it for the same 30 days as the server."""
    token = request.cookies.get(COOKIE)
    if token:
        with session_scope(_shared(request)) as session:
            seen = auth.session_user(session, token, datetime.now(UTC))
        if seen is not None:
            if seen.renewed:
                _set_cookie(response, token)
            return seen.user_id
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sign in first")


Owner = Annotated[int, Depends(owner)]


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(auth.SESSION_TTL.total_seconds()),
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )


@router.post("/redeem", status_code=status.HTTP_204_NO_CONTENT)
def redeem(body: Redeem, request: Request, response: Response) -> None:
    """Exchange a one-time link from the bot for a session cookie."""
    label = request.headers.get("user-agent", "")
    with session_scope(_shared(request)) as session:
        cookie = auth.redeem_link(session, body.token, datetime.now(UTC), label)
    if cookie is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "this link has expired or was used")
    _set_cookie(response, cookie)


@router.get("/me", response_model=Me)
def me(user: Owner) -> Me:
    return Me(user_id=user)


@router.post("/signout", status_code=status.HTTP_204_NO_CONTENT)
def signout(request: Request, response: Response) -> None:
    """End this browser's session. Harmless without one."""
    token = request.cookies.get(COOKIE)
    if token:
        with session_scope(_shared(request)) as session:
            auth.end_session(session, token, datetime.now(UTC))
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="strict")
