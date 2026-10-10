"""The person's own AI key for comments (ADR-0047 B). Owner-only. The key goes in once, is
checked with Groq, stored encrypted and never sent back: only its last four characters."""

from datetime import UTC, datetime
from typing import Annotated

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from pydantic import BaseModel, Field, SecretStr, StringConstraints
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.alerts import alert
from training_coach.api.auth import Fresh, Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import ai_key
from training_coach.services.groq import GroqClient, GroqUnavailableError
from training_coach.services.secret_box import SecretBox

router = APIRouter(prefix="/api/account/ai", tags=["account"])
log = structlog.get_logger(__name__)

# Groq keys are "gsk_" and letters and digits; anything else can't be one, so it never leaves.
GroqKey = Annotated[str, StringConstraints(pattern=r"^gsk_[A-Za-z0-9]{20,200}$")]


class AiView(BaseModel):
    available: bool  # False until the server has TC_SECRETS_KEY
    connected: bool
    ends_in: str | None
    enabled: bool
    body: bool
    readiness: bool
    failed: bool  # the key stopped working: enter it again


class KeyBody(BaseModel):
    key: GroqKey = Field(repr=False)


class OptionsBody(BaseModel):
    enabled: bool
    body: bool
    readiness: bool


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _box(request: Request) -> SecretBox | None:
    settings: Settings = request.app.state.settings
    return SecretBox(settings.secrets_key) if settings.secrets_key is not None else None


def _view(request: Request, user: int) -> AiView:
    with session_scope(_bound(request, user)) as session:
        found = ai_key.status(session)
    return AiView(available=_box(request) is not None, **vars(found))


async def _check(key: SecretStr) -> None:
    try:
        await GroqClient(key, attempts=2, deadline=15.0).verify()
    except GroqUnavailableError as exc:
        log.info("ai.key_check_failed", reason=exc.reason)
        if exc.reason in {"http_401", "http_403"}:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Groq didn't accept that key") from exc
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Couldn't reach Groq to check the key"
        ) from exc


@router.get("", response_model=AiView)
def get_ai(request: Request, user: Owner) -> AiView:
    return _view(request, user)


@router.put("/key", response_model=AiView)
async def store_key(
    body: KeyBody, request: Request, background: BackgroundTasks, user: Owner, _fresh: Fresh
) -> AiView:
    """Check the key with Groq, then keep it encrypted. Needs a recent sign-in and is alerted:
    whoever holds the key's account can see what is sent to it."""
    box = _box(request)
    if box is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "AI keys aren't set up on this server")
    key = SecretStr(body.key)
    await _check(key)
    with session_scope(_bound(request, user)) as session:
        ai_key.store(session, box, key)
    alert(request, background, "ai_key_stored", "An AI key was added to Training Coach.")
    return _view(request, user)


@router.delete("/key", status_code=status.HTTP_204_NO_CONTENT)
def remove_key(request: Request, background: BackgroundTasks, user: Owner) -> None:
    """Remove the key. No fresh sign-in (removing sends nothing anywhere), but alerted, so a
    removal from a stolen session doesn't go unnoticed."""
    with session_scope(_bound(request, user)) as session:
        if not ai_key.remove(session):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no AI key stored")
    alert(request, background, "ai_key_removed", "Your AI key was removed from Training Coach.")


@router.put("", response_model=AiView)
def set_options(body: OptionsBody, request: Request, user: Owner) -> AiView:
    with session_scope(_bound(request, user)) as session:
        if not ai_key.options(
            session, enabled=body.enabled, body=body.body, readiness=body.readiness
        ):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no AI key stored")
    return _view(request, user)


@router.post("/test", status_code=status.HTTP_204_NO_CONTENT)
async def test_key(request: Request, user: Owner) -> None:
    """Check the stored key still works, and record the answer: a refused key is marked
    failed, a working one clears an earlier failure, so the status matches the check."""
    box = _box(request)
    if box is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "AI keys aren't set up on this server")
    now = datetime.now(UTC)
    with session_scope(_bound(request, user)) as session:
        key = ai_key.key(session, box, now)
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no readable AI key stored")
    try:
        await _check(key)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_400_BAD_REQUEST:
            with session_scope(_bound(request, user)) as session:
                ai_key.failed(session, now)
        raise
    with session_scope(_bound(request, user)) as session:
        ai_key.working(session)
