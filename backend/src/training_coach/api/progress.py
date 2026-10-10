"""Each exercise's standing for the web Progress page, as /progress in the bot. Owner-only."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.api.session import UNITS
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import progress

router = APIRouter(prefix="/api/progress", tags=["progress"])


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


class StandingView(BaseModel):
    exercise: str
    unit: Literal["reps", "seconds", "minutes"]
    step: str
    step_number: int
    steps: int
    last: list[int]  # the latest session at this step, per set; empty if none yet
    best_set: int | None
    status: Literal["hold", "ready", "top_of_ladder"]
    retired: bool
    recent: list[int]  # best set per session at this step, newest first


@router.get("", response_model=list[StandingView])
def standings(request: Request, user: Owner) -> list[StandingView]:
    """Every exercise in plan order: its step, last session, best set and whether it's ready."""
    with session_scope(_bound(request, user)) as session:
        found = progress.overview(session)
    return [
        StandingView(
            exercise=s.exercise,
            unit=UNITS[s.kind],
            step=s.step,
            step_number=s.step_number,
            steps=s.steps,
            last=list(s.last),
            best_set=s.best_set,
            status=s.status.value,
            retired=s.retired,
            recent=list(s.recent),
        )
        for s in found
    ]
