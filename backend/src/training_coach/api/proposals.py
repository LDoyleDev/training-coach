"""Logs a connected AI proposed, on Today (ADR-0058): Save or Discard. Owner-only, by session
cookie: ``/api/*`` never takes a bearer token, so no AI app can save or discard its own
proposal. Saving goes through the service of that kind of log, so /undo takes a workout back."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request, status
from pydantic import BaseModel

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import proposals

router = APIRouter(prefix="/api/proposals", tags=["proposals"])
Token = Annotated[str, Path(pattern="^[0-9a-f]{32}$")]


class ProposalView(BaseModel):
    token: str
    kind: str  # strength, cardio, habits or body
    on: date
    source: str  # the app's name as it claimed it: shown as a claim, never trusted
    summary: str  # exactly what Save writes
    expires_at: datetime


class ProposalSaved(BaseModel):
    summary: str
    workout: bool  # a workout was saved: Undo can take it back


@router.get("", response_model=list[ProposalView])
def waiting(request: Request, user: Owner) -> list[ProposalView]:
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        found = proposals.pending(session, datetime.now(UTC))
    return [
        ProposalView(
            token=p.token,
            kind=p.kind,
            on=p.on,
            source=p.source,
            summary=p.summary,
            expires_at=p.expires_at,
        )
        for p in found
    ]


@router.post("/{token}/save", response_model=ProposalSaved)
def save(token: Token, request: Request, user: Owner) -> ProposalSaved:
    """Save it. 404 when it has expired or never was; 409 with ``already_saved`` or
    ``already_discarded`` when it was dealt with (here or in Telegram); 409 with the reason
    when it no longer fits (it is discarded then)."""
    settings: Settings = request.app.state.settings
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        result = proposals.save(session, token, settings.tz, datetime.now(UTC), "web")
    if isinstance(result, proposals.Gone):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "that proposal has gone")
    if isinstance(result, proposals.Already):
        raise HTTPException(status.HTTP_409_CONFLICT, f"already_{result.status}")
    if isinstance(result, proposals.Changed):
        raise HTTPException(status.HTTP_409_CONFLICT, result.reason)
    return ProposalSaved(summary=result.summary, workout=result.workout)


@router.post("/{token}/discard", status_code=status.HTTP_204_NO_CONTENT)
def discard(token: Token, request: Request, user: Owner) -> None:
    """Discard it; nothing is saved. Discarding one already dealt with changes nothing."""
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        result = proposals.discard(session, token, datetime.now(UTC), "web")
    if isinstance(result, proposals.Gone):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "that proposal has gone")
