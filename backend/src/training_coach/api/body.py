"""Body measurements for the web app (2-B, #142; the protocol and the estimate, ADR-0076).
Owner-only; never in a share view."""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.measurements import CADENCE, CHECKLIST, SPECS, Kind, how
from training_coach.domain.queue import local_date
from training_coach.services import measurements

router = APIRouter(prefix="/api/body", tags=["body"])

KindName = Literal[
    "bodyweight",
    "body_fat_scale",
    "waist",
    "neck",
    "chest",
    "upper_arm",
    "thigh",
    "resting_hr",
]


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
    how: str  # how to take it the same way each time; the thigh at the person's distance


@router.get("/kinds", response_model=list[KindView])
def kinds(request: Request, user: Owner) -> list[KindView]:
    """What can be measured, in order, with units, ranges and how to take each."""
    with session_scope(_bound(request, user)) as session:
        offset = measurements.body_settings(session).thigh_offset_cm
    return [
        KindView(
            kind=k.value,
            label=s.label,
            unit=s.unit,
            decimals=s.decimals,
            low=s.low,
            high=s.high,
            how=how(k, offset),
        )
        for k, s in SPECS.items()
    ]


class GuideView(BaseModel):
    checklist: list[str]  # before measuring anything, in order
    cadence: str  # how often


@router.get("/guide", response_model=GuideView)
def guide(user: Owner) -> GuideView:
    """The "Before you measure" checklist and how often to measure."""
    return GuideView(checklist=list(CHECKLIST), cadence=CADENCE)


class EstimateView(BaseModel):
    on: date
    value: float


@router.get("/estimates", response_model=list[EstimateView])
def estimates(request: Request, user: Owner) -> list[EstimateView]:
    """The tape body-fat estimate (%, ±4) for each day with a waist and a neck, newest first;
    empty unless the estimate is turned on and the height is set. Worked out, never stored."""
    with session_scope(_bound(request, user)) as session:
        found = measurements.estimates(session)
    return [EstimateView(on=p.on, value=p.value) for p in found]


class AverageView(BaseModel):
    on: date
    value: float  # kg: the mean of the weigh-ins in the 7 days ending ``on``
    count: int  # how many weigh-ins that is


@router.get("/averages", response_model=list[AverageView])
def averages(request: Request, user: Owner) -> list[AverageView]:
    """Bodyweight's 7-day average at each day with a weigh-in, newest first: the first is the
    latest, the rest are its trend."""
    with session_scope(_bound(request, user)) as session:
        found = measurements.averages(session)
    return [AverageView(on=a.on, value=a.value, count=a.count) for a in found]


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


class MeasureSaved(BaseModel):
    # "Waist is 3.5 cm off your last (12 Oct): different landmark? Re-measure.": saved anyway.
    warnings: list[str]


@router.put("", response_model=MeasureSaved)
def save(body: MeasureBody, request: Request, user: Owner) -> MeasureSaved:
    """Save a day's measurements (any of them), replacing the same kind that day; with a
    warning for each one far from the last earlier entry of its kind."""
    today = _today(request)
    on = body.on or today
    values = {Kind(k): v for k, v in body.values.items()}
    with session_scope(_bound(request, user)) as session:
        problem = measurements.save(session, on, today, values)  # all or none
        warnings = [] if problem is not None else measurements.remeasure(session, on, values)
    if problem is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    return MeasureSaved(warnings=warnings)


@router.delete("/{on}/{kind}", status_code=status.HTTP_204_NO_CONTENT)
def remove(on: date, kind: KindName, request: Request, user: Owner) -> None:
    with session_scope(_bound(request, user)) as session:
        removed = measurements.delete(session, on, Kind(kind))
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such measurement")
