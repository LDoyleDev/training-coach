"""A log for a day that already has its session (ADR-0060): the 409 that shows what is there,
and the person's answer, sent back with the same save.

The answer names the workouts the browser showed (``seen``); the service checks them again
when it saves, so a day that changed meanwhile is asked about again rather than overwritten.
"""

from datetime import date
from typing import Any

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from training_coach.services import day_clash


class RecordedView(BaseModel):
    workout_id: int
    name: str  # "Legs", "Rest day"
    summary: str  # "12 sets: Squat, Lunge, Calf raise", "45 min", "rested"


class ClashView(BaseModel):
    """What is already saved for ``day``. ``moving``: it is the day the old workout would have
    moved to, which holds a session too: pick another day."""

    day: date
    recorded: list[RecordedView]
    moving: bool


class ClashConflict(BaseModel):
    detail: ClashView | str  # a ClashView when the day already has its session


# For the API types: a save's 409 may carry what is already saved that day.
CLASH: dict[int | str, dict[str, Any]] = {
    status.HTTP_409_CONFLICT: {
        "model": ClashConflict,
        "description": "The day already has its session (a ClashView), or today changed",
    }
}


class ClashReply(BaseModel):
    """The person's answer to a clash: ``replace``, ``add`` or ``move:YYYY-MM-DD``, with the ids
    of the workouts they were shown. Left out on the first try."""

    resolution: str | None = Field(
        default=None, pattern=r"^(?:replace|add|move:\d{4}-\d{2}-\d{2})$"
    )
    seen: list[int] = Field(default_factory=list, max_length=20)


def resolution(body: ClashReply) -> day_clash.Resolution | None:
    """The answer for the service, or None when there is none. 422 for a date that isn't one."""
    if body.resolution is None:
        return None
    found = day_clash.parse(body.resolution, body.seen)
    if found is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "that isn't a date")
    return found


def conflict(found: day_clash.Clash | day_clash.Refused) -> HTTPException:
    """The answer to a save that didn't happen: ask (409 with what is there), or say why not."""
    if isinstance(found, day_clash.Refused):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, found.reason)
    view = ClashView(
        day=found.day,
        recorded=[RecordedView(**vars(r)) for r in found.recorded],
        moving=found.moving,
    )
    return HTTPException(status.HTTP_409_CONFLICT, view.model_dump(mode="json"))
