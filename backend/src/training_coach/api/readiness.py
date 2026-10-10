"""The readiness questions for the web app (ADR-0046). Owner-only; health data, never shared."""

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.readiness import KEYS, QUESTIONS, RENEW
from training_coach.domain.readiness import status as readiness_status
from training_coach.services import readiness

router = APIRouter(prefix="/api/readiness", tags=["readiness"])

StatusName = Literal["due", "clear", "see_doctor"]


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


class QuestionView(BaseModel):
    key: str
    text: str


class ReadinessView(BaseModel):
    """The questions, the latest answers if they still count, and what they mean."""

    questions: list[QuestionView]
    status: StatusName
    answers: dict[str, bool] | None  # None when due: asked again from scratch
    answered_at: datetime | None
    ask_again_after: datetime | None


@router.get("", response_model=ReadinessView)
def get_readiness(request: Request, user: Owner) -> ReadinessView:
    now = datetime.now(UTC)
    with session_scope(_bound(request, user)) as session:
        row = readiness.latest(session)
        answers = dict(row.answers) if row is not None else None
        version = row.version if row is not None else None
        answered = row.answered_at if row is not None else None
    current = readiness_status(answers, version, answered, now)
    counts = current != "due" and answered is not None
    return ReadinessView(
        questions=[QuestionView(key=q.key, text=q.text) for q in QUESTIONS],
        status=current.value,
        answers=answers if counts else None,
        answered_at=answered if counts else None,
        ask_again_after=answered + RENEW if counts and answered is not None else None,
    )


class AnswersBody(BaseModel):
    answers: dict[str, bool] = Field(max_length=len(QUESTIONS))


class ReadinessSavedView(BaseModel):
    status: StatusName


@router.put("", response_model=ReadinessSavedView)
def put_readiness(body: AnswersBody, request: Request, user: Owner) -> ReadinessSavedView:
    """Answer every question; the answers replace any earlier ones."""
    if set(body.answers) != KEYS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "answer every question")
    with session_scope(_bound(request, user)) as session:
        current = readiness.save(session, body.answers, datetime.now(UTC))
    return ReadinessSavedView(status=current.value)
