"""What the band says (ADR-0055): last night's sleep, steps and resting heart rate, small on
Home and Progress. Owner-only; health data, never shared."""

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import health_summary

router = APIRouter(prefix="/api/health", tags=["health"])


class NightView(BaseModel):
    start: datetime
    end: datetime
    asleep: int  # minutes
    awake: int
    light: int
    deep: int
    rem: int


class HealthView(BaseModel):
    """Everything empty until band data arrives."""

    sleep: NightView | None
    steps_today: int | None
    steps_yesterday: int | None
    resting: int | None
    usual_resting: int | None


@router.get("", response_model=HealthView)
def get_health(request: Request, user: Owner) -> HealthView:
    settings: Settings = request.app.state.settings
    today = local_date(datetime.now(UTC), settings.tz)
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        found = health_summary.summary(session, today)
    night = NightView.model_validate(vars(found.sleep)) if found.sleep is not None else None
    return HealthView(
        sleep=night,
        steps_today=found.steps_today,
        steps_yesterday=found.steps_yesterday,
        resting=found.resting,
        usual_resting=found.usual_resting,
    )
