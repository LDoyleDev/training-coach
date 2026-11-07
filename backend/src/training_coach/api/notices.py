"""What a release changed in the person's plan (ADR-0087), until they've seen it. Owner-only."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request, status
from pydantic import BaseModel, Field

from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import plan_notices

router = APIRouter(prefix="/api/notices", tags=["notices"])


class NoticeView(BaseModel):
    id: int
    text: str


class ReadBody(BaseModel):
    ids: list[int] = Field(max_length=200)


@router.get("", response_model=list[NoticeView])
def get_notices(request: Request, user: Owner) -> list[NoticeView]:
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        return [NoticeView(id=n.id, text=n.text) for n in plan_notices.unread(session)]


@router.post("/read", status_code=status.HTTP_204_NO_CONTENT)
def read_notices(request: Request, user: Owner, body: ReadBody) -> None:
    """ "Got it": these won't show again."""
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        plan_notices.mark_read(session, body.ids, datetime.now(UTC))
