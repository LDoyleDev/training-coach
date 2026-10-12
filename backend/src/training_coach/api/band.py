"""Workouts from the band to count as cardio, on Today (ADR-0055). Owner-only. Counting is one
tap and goes through the cardio log, so it is idempotent and /undo takes it back."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from training_coach.api.auth import Owner
from training_coach.api.cardio import WeekView, week_view
from training_coach.api.clash import CLASH, ClashReply, conflict, resolution
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import CardioActivity
from training_coach.domain.queue import local_date
from training_coach.services import band_cardio, cardio, workout_log
from training_coach.services.day_clash import Clash, Refused

router = APIRouter(prefix="/api/band/offers", tags=["band"])


class BandOfferView(BaseModel):
    id: int
    on: date
    activity: CardioActivity
    minutes: int
    zone2: int | None  # minutes in zone 2; None without heart rate
    kind: str  # zone2 or moderate-cardio
    value: int  # the minutes it counts for
    text: str


class BandCounted(BaseModel):
    workout_id: int
    already_saved: bool
    planned: bool  # it completed today's planned session
    week: WeekView


def _today(request: Request) -> date:
    settings: Settings = request.app.state.settings
    return local_date(datetime.now(UTC), settings.tz)


@router.get("", response_model=list[BandOfferView])
def offers(request: Request, user: Owner) -> list[BandOfferView]:
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        found = band_cardio.offers(session, _today(request))
    return [BandOfferView.model_validate(vars(o)) for o in found]


@router.post("/{import_id}/count", response_model=BandCounted, responses=CLASH)
def count(
    import_id: int, request: Request, user: Owner, body: ClashReply | None = None
) -> BandCounted:
    """Count a band workout as cardio. 404 when it isn't on offer; 409 when today's session
    changed in a way that makes it stale (count it again), or with what is saved already when
    the day has its session (ADR-0060): count it again with the answer."""
    settings: Settings = request.app.state.settings
    today = _today(request)
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        answer = resolution(body) if body is not None else None
        result = band_cardio.count(session, import_id, today, settings.tz, answer)
        if isinstance(result, Clash | Refused):
            raise conflict(result)
        if isinstance(result, band_cardio.Gone):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "that workout isn't on offer")
        if isinstance(result, workout_log.Stale):
            raise HTTPException(status.HTTP_409_CONFLICT, "today's session has changed")
        return BandCounted(
            workout_id=result.workout_id,
            already_saved=result.already,
            planned=result.planned,
            week=week_view(cardio.week(session, today)),
        )


@router.post("/{import_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(import_id: int, request: Request, user: Owner) -> None:
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        if not band_cardio.dismiss(session, import_id):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no such workout")
