"""The AI apps a person has connected (ADR-0047 C): listed on the Account page, each revocable
at once (mcp-threat-model.md M12, requirement 19). Owner-only."""

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from pydantic import BaseModel

from training_coach.api.alerts import alert
from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import mcp_tokens

router = APIRouter(prefix="/api/account/connections", tags=["account"])


class ConnectionView(BaseModel):
    id: int
    client_name: str  # what the app called itself: a claim, not a fact
    redirect_host: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    ends_at: datetime


@router.get("", response_model=list[ConnectionView])
def list_connections(request: Request, user: Owner) -> list[ConnectionView]:
    bound = make_session_factory(request.app.state.engine, user_id=user)
    with session_scope(bound) as session:
        found = mcp_tokens.live_connections(session, datetime.now(UTC))
    return [ConnectionView(**vars(c)) for c in found]


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_connection(
    connection_id: int, request: Request, background: BackgroundTasks, user: Owner
) -> None:
    """Revoke: its access and refresh tokens stop working at once. Like signing out a device,
    it needs no fresh sign-in: it only ever takes access away."""
    bound = make_session_factory(request.app.state.engine, user_id=user)
    with session_scope(bound) as session:
        revoked = mcp_tokens.revoke(session, connection_id, datetime.now(UTC))
    if not revoked:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such connection")
    alert(
        request,
        background,
        "mcp_revoked",
        "An AI app's connection to Training Coach was revoked. It can't read anything now.",
    )
