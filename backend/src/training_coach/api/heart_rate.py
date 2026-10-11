"""Heart-rate zones on Account (ADR-0055): what they are and what they come from, and the
birth year and own max heart rate that set them. Owner-only."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import health_import, zones

router = APIRouter(prefix="/api/account/heart-rate", tags=["account"])


class ZoneView(BaseModel):
    zone: int  # 1-5
    low: int  # bpm, from
    high: int  # bpm, up to (not including)


class HeartRateView(BaseModel):
    birth_year: int | None
    own_max: int | None  # typed in; wins over everything
    estimated_max: int | None  # 208 - 0.7 x age, without one of their own
    peak: int | None  # the highest any imported workout reached
    rest: int  # resting heart rate used: the median of the last 7 nights
    max: int  # max heart rate used
    zones: list[ZoneView]


class HeartRateBody(BaseModel):
    birth_year: int | None = None
    own_max: int | None = None


def _view(found: zones.HeartRate) -> HeartRateView:
    hr = found.zones
    return HeartRateView(
        birth_year=found.birth_year,
        own_max=found.own_max,
        estimated_max=found.estimated_max,
        peak=found.peak,
        rest=hr.rest,
        max=hr.max,
        zones=[ZoneView(zone=n, low=lo, high=hi) for n, (lo, hi) in enumerate(hr.bounds, 1)],
    )


@router.get("", response_model=HeartRateView)
def get_heart_rate(request: Request, user: Owner) -> HeartRateView:
    settings: Settings = request.app.state.settings
    today = local_date(datetime.now(UTC), settings.tz)
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        return _view(zones.current(session, today))


@router.put("", response_model=HeartRateView)
def set_heart_rate(body: HeartRateBody, request: Request, user: Owner) -> HeartRateView:
    """Save the birth year and own max (either empty), and count recent zone minutes again."""
    settings: Settings = request.app.state.settings
    now = datetime.now(UTC)
    today = local_date(now, settings.tz)
    if (problem := zones.problem(body.birth_year, body.own_max, today.year)) is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        zones.save(session, body.birth_year, body.own_max)
        health_import.rezone(session, today, now)
        return _view(zones.current(session, today))
