"""Logs a connected AI proposed, on Today (ADR-0058): Save or Discard. Owner-only, by session
cookie: ``/api/*`` never takes a bearer token, so no AI app can save or discard its own
proposal. Saving goes through the service of that kind of log, so /undo takes a workout back.
The token travels in the request body, never in a URL that an access log could keep."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from training_coach.api.auth import Owner
from training_coach.api.clash import CLASH, ClashReply, conflict, resolution
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import day_clash, proposals

router = APIRouter(prefix="/api/proposals", tags=["proposals"])


class ProposalView(BaseModel):
    token: str
    kind: str  # strength, cardio, habits or body
    on: date
    source: str  # the app's name as it claimed it: shown as a claim, never trusted
    summary: str  # exactly what Save writes
    replaces: str | None  # "Replaces the 78.4 kg saved that day": shown here, never to the AI
    expires_at: datetime
    # Cardio: the kind the coach suggests and why ("Average 131 bpm is in your zone 2 ..."); the
    # person picks zone 2 or moderate on the card (ADR-0067, 2026-10-24).
    suggested: proposals.CardioKind | None = None
    suggestion: str | None = None
    # Body: "Waist is 3.5 cm off your last (12 Oct): different landmark? Re-measure." (ADR-0076)
    warnings: list[str] = []


class ProposalToken(BaseModel):
    token: str = Field(pattern="^[0-9a-f]{32}$")


class ProposalSave(ClashReply):
    """The token, and the answer when the day already has its session (ADR-0060)."""

    token: str = Field(pattern="^[0-9a-f]{32}$")
    # How hard a cardio one felt, 1-10 (ADR-0067): the person picks it on the card, the AI
    # never sends it. Ignored for the other kinds.
    effort: int | None = Field(default=None, ge=1, le=10)
    # Whether a cardio one was zone 2 or moderate: the person picks it, the AI only hints.
    cardio: proposals.CardioKind | None = None


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
            replaces=p.replaces,
            expires_at=p.expires_at,
            suggested=p.suggested,
            suggestion=p.suggestion,
            warnings=list(p.warnings),
        )
        for p in found
    ]


@router.post("/save", response_model=ProposalSaved, responses=CLASH)
def save(body: ProposalSave, request: Request, user: Owner) -> ProposalSaved:
    """Save it. 404 when it has expired or never was; 409 with ``already_saved`` or
    ``already_discarded`` when it was dealt with (here or in Telegram); 409 with the reason
    when it no longer fits (it is discarded then); 409 with what is saved already when its
    day has its session (it keeps waiting: save it again with the answer, ADR-0060); 422 for
    a cardio one without zone 2 or moderate picked (it keeps waiting)."""
    settings: Settings = request.app.state.settings
    answer = resolution(body)
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        result = proposals.save(
            session,
            body.token,
            settings.tz,
            datetime.now(UTC),
            "web",
            answer,
            body.effort,
            body.cardio,
        )
    if isinstance(result, day_clash.Clash | day_clash.Refused):
        raise conflict(result)
    if isinstance(result, proposals.Gone):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "that proposal has gone")
    if isinstance(result, proposals.Unpicked):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "pick zone 2 or moderate")
    if isinstance(result, proposals.Already):
        raise HTTPException(status.HTTP_409_CONFLICT, f"already_{result.status}")
    if isinstance(result, proposals.Changed):
        raise HTTPException(status.HTTP_409_CONFLICT, result.reason)
    return ProposalSaved(summary=result.summary, workout=result.workout)


@router.post("/discard", status_code=status.HTTP_204_NO_CONTENT)
def discard(body: ProposalToken, request: Request, user: Owner) -> None:
    """Discard it; nothing is saved. Discarding one already dealt with changes nothing."""
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        result = proposals.discard(session, body.token, datetime.now(UTC), "web")
    if isinstance(result, proposals.Gone):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "that proposal has gone")
