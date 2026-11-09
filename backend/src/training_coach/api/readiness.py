"""The health questions for the web app (ADR-0085). The browser asks them, works out the note
and keeps the answers on the device; this only says whether they're due and records that they
were answered. Not health data, so members use it with no consent asked (ADR-0090)."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.readiness import RENEW, VERSION, due
from training_coach.services import readiness

router = APIRouter(prefix="/api/readiness", tags=["readiness"])


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


class ReadinessView(BaseModel):
    """Which questions the server expects, and when they were last answered, if that counts."""

    version: int
    due: bool
    answered_at: datetime | None
    ask_again_after: datetime | None


def readiness_view(version: int | None, answered: datetime | None, now: datetime) -> ReadinessView:
    is_due = due(version, answered, now)
    counts = not is_due and answered is not None
    return ReadinessView(
        version=VERSION,
        due=is_due,
        answered_at=answered if counts else None,
        ask_again_after=answered + RENEW if counts and answered is not None else None,
    )


@router.get("", response_model=ReadinessView)
def get_readiness(request: Request, user: Owner) -> ReadinessView:
    with session_scope(_bound(request, user)) as session:
        row = readiness.latest(session)
        version, answered = (row.version, row.answered_at) if row else (None, None)
    return readiness_view(version, answered, datetime.now(UTC))


class AnsweredBody(BaseModel):
    version: int  # the questions the browser asked: no answers, ever


@router.put("", response_model=ReadinessView)
def put_readiness(body: AnsweredBody, request: Request, user: Owner) -> ReadinessView:
    """Record that the current questions were answered now. 409 if the browser asked an older
    version (a page loaded before a release): it reloads and asks the new ones."""
    if body.version != VERSION:
        raise HTTPException(status.HTTP_409_CONFLICT, "the questions changed: reload the page")
    now = datetime.now(UTC)
    with session_scope(_bound(request, user)) as session:
        row = readiness.answered(session, now)
        version, answered = row.version, row.answered_at
    return readiness_view(version, answered, now)
