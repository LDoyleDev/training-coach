"""Body measurements for the web app (2-B, #142). Owner-only; never in a share view."""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.measurements import SPECS, Kind
from training_coach.domain.queue import local_date
from training_coach.services import measurements

router = APIRouter(prefix="/api/body", tags=["body"])

KindName = Literal["bodyweight", "waist", "chest", "upper_arm", "thigh", "resting_hr"]


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _today(request: Request) -> date:
    settings: Settings = request.app.state.settings
    return local_date(datetime.now(UTC), settings.tz)


class KindView(BaseModel):
    kind: KindName
    label: str
    unit: str
    decimals: int
    low: float
    high: float


@router.get("/kinds", response_model=list[KindView])
def kinds(user: Owner) -> list[KindView]:
    """What can be measured, in order, with units and ranges."""
    return [
        KindView(
            kind=k.value, label=s.label, unit=s.unit, decimals=s.decimals, low=s.low, high=s.high
        )
        for k, s in SPECS.items()
    ]


class MeasurementView(BaseModel):
    on: date
    kind: KindName
    value: float


@router.get("", response_model=list[MeasurementView])
def history(request: Request, user: Owner) -> list[MeasurementView]:
    """Every measurement, newest day first."""
    with session_scope(_bound(request, user)) as session:
        entries = measurements.history(session)
    return [MeasurementView(on=e.on, kind=e.kind.value, value=e.value) for e in entries]


class MeasureBody(BaseModel):
    on: date | None = None  # default today; up to 14 days back
    values: dict[KindName, float] = Field(max_length=len(SPECS))


@router.put("", status_code=status.HTTP_204_NO_CONTENT)
def save(body: MeasureBody, request: Request, user: Owner) -> None:
    """Save a day's measurements (any of them), replacing the same kind that day."""
    today = _today(request)
    values = {Kind(k): v for k, v in body.values.items()}
    with session_scope(_bound(request, user)) as session:
        problem = measurements.save(session, body.on or today, today, values)  # all or none
    if problem is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)


@router.delete("/{on}/{kind}", status_code=status.HTTP_204_NO_CONTENT)
def remove(on: date, kind: KindName, request: Request, user: Owner) -> None:
    with session_scope(_bound(request, user)) as session:
        removed = measurements.delete(session, on, Kind(kind))
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such measurement")
