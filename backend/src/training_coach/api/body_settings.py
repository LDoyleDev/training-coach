"""Body settings on Account (ADR-0074): height for the tape estimate, how far above the kneecap
the thigh is measured, and whether the body-fat estimate is worked out. Owner-only."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.measurements import (
    DEFAULT_THIGH_OFFSET_CM,
    BodyFatEstimate,
    settings_problem,
)
from training_coach.services import measurements

router = APIRouter(prefix="/api/account/body", tags=["account"])

EstimateName = Literal["off", "navy_male"]


class BodySettingsView(BaseModel):
    height_cm: int | None
    thigh_offset_cm: int  # cm above the top of the kneecap
    body_fat_estimate: EstimateName  # navy_male: from waist, neck and height, ±4%


class BodySettingsBody(BaseModel):
    height_cm: int | None = None
    thigh_offset_cm: int = DEFAULT_THIGH_OFFSET_CM
    body_fat_estimate: EstimateName = "off"


def _view(found: measurements.BodySettings) -> BodySettingsView:
    return BodySettingsView(
        height_cm=found.height_cm,
        thigh_offset_cm=found.thigh_offset_cm,
        body_fat_estimate=found.body_fat_estimate.value,
    )


@router.get("", response_model=BodySettingsView)
def get_body_settings(request: Request, user: Owner) -> BodySettingsView:
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        return _view(measurements.body_settings(session))


@router.put("", response_model=BodySettingsView)
def set_body_settings(body: BodySettingsBody, request: Request, user: Owner) -> BodySettingsView:
    """Save all three (the height may be empty)."""
    if (problem := settings_problem(body.height_cm, body.thigh_offset_cm)) is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    chosen = measurements.BodySettings(
        body.height_cm, body.thigh_offset_cm, BodyFatEstimate(body.body_fat_estimate)
    )
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        measurements.save_settings(session, chosen)
        return _view(measurements.body_settings(session))
