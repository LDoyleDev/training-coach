"""Baseline tests and retests for the web app (2-A, #94, ADR-0037). Owner-only."""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.enums import Side
from training_coach.domain.fitness_tests import RANGES, Result, TimeOfDay
from training_coach.domain.queue import local_date
from training_coach.services import fitness_tests

router = APIRouter(prefix="/api/tests", tags=["tests"])

Unit = Literal["reps", "seconds", "metres", "cm"]
When = Literal["morning", "midday", "afternoon", "evening"]
SideName = Literal["both", "left", "right"]


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _today(request: Request) -> date:
    settings: Settings = request.app.state.settings
    return local_date(datetime.now(UTC), settings.tz)


class TestView(BaseModel):
    slug: str
    name: str
    day: int
    unit: Unit
    per_side: bool
    cue: str
    low: int  # the result's allowed range
    high: int


@router.get("", response_model=list[TestView])
def definitions(user: Owner) -> list[TestView]:
    """Every test, day 1 first."""
    return [
        TestView(
            slug=t.slug,
            name=t.name,
            day=t.day,
            unit=t.unit.value,
            per_side=t.per_side,
            cue=t.cue,
            low=RANGES[t.unit][0],
            high=RANGES[t.unit][1],
        )
        for t in fitness_tests.tests()
    ]


class ResultView(BaseModel):
    test: str = Field(max_length=64)
    side: SideName
    value: int


class TestDayBody(BaseModel):
    day: int
    on: date | None = None  # default today; up to 14 days back
    time_of_day: When
    fed: bool
    slept_well: bool
    results: list[ResultView] = Field(max_length=40)
    token: str = Field(min_length=16, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")


class SavedView(BaseModel):
    id: int
    already_saved: bool


@router.post("", response_model=SavedView)
def save(body: TestDayBody, request: Request, user: Owner) -> SavedView:
    """Save a test day once (a repeated Save with the same token returns it)."""
    today = _today(request)
    conditions = fitness_tests.Conditions(TimeOfDay(body.time_of_day), body.fed, body.slept_well)
    results = [Result(r.test, Side(r.side), r.value) for r in body.results]
    with session_scope(_bound(request, user)) as session:
        saved = fitness_tests.save(
            session, body.on or today, today, body.day, conditions, results, body.token
        )
    if isinstance(saved, str):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, saved)
    return SavedView(id=saved.id, already_saved=saved.already_saved)


class DayView(BaseModel):
    id: int
    on: date
    day: int
    time_of_day: When
    fed: bool
    slept_well: bool
    results: list[ResultView]


@router.get("/results", response_model=list[DayView])
def results(request: Request, user: Owner) -> list[DayView]:
    """Every test day, newest first."""
    with session_scope(_bound(request, user)) as session:
        days = fitness_tests.history(session)
    return [
        DayView(
            id=d.id,
            on=d.on,
            day=d.day,
            time_of_day=d.conditions.time_of_day.value,
            fed=d.conditions.fed,
            slept_well=d.conditions.slept_well,
            results=[ResultView(test=r.test, side=r.side.value, value=r.value) for r in d.results],
        )
        for d in days
    ]
