"""Progress photos for the web app (2-B, #143, ADR-0039). Owner-only; never in a share view.

An upload is the JPEG itself as the request body (no form encoding, so no multipart parser),
read up to the size limit and no further.
"""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.photos import MAX_BYTES, Pose
from training_coach.domain.queue import local_date
from training_coach.services import photos

router = APIRouter(prefix="/api/photos", tags=["photos"])

PoseName = Literal["front", "side", "back"]
JPEG = "image/jpeg"


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


class PhotoView(BaseModel):
    id: int
    on: date
    pose: PoseName
    size: int


@router.get("", response_model=list[PhotoView])
def listing(request: Request, user: Owner) -> list[PhotoView]:
    """Every photo, newest day first (no pictures, just what there is)."""
    with session_scope(_bound(request, user)) as session:
        found = photos.listing(session)
    return [PhotoView(id=p.id, on=p.on, pose=p.pose.value, size=p.size) for p in found]


class SavedPhoto(BaseModel):
    id: int


async def _body(request: Request) -> bytes:
    """The request body, refused as soon as it passes the limit."""
    if request.headers.get("content-type", "").split(";")[0].strip() != JPEG:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "send the photo as a JPEG")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "the photo is too large")
    return bytes(data)


@router.put("/{on}/{pose}", response_model=SavedPhoto)
async def upload(on: date, pose: PoseName, request: Request, user: Owner) -> SavedPhoto:
    """Store a photo for a day and pose, replacing one already there; its metadata is removed."""
    data = await _body(request)
    settings: Settings = request.app.state.settings
    today = local_date(datetime.now(UTC), settings.tz)
    with session_scope(_bound(request, user)) as session:
        saved = photos.save(session, on, today, Pose(pose), data)
    if isinstance(saved, str):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, saved)
    return SavedPhoto(id=saved)


@router.get("/{photo_id}", response_class=Response, responses={200: {"content": {JPEG: {}}}})
def picture(photo_id: int, request: Request, user: Owner) -> Response:
    """One photo. Never cached anywhere but in memory."""
    with session_scope(_bound(request, user)) as session:
        data = photos.picture(session, photo_id)
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such photo")
    return Response(data, media_type=JPEG, headers={"Cache-Control": "private, no-store"})


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(photo_id: int, request: Request, user: Owner) -> None:
    with session_scope(_bound(request, user)) as session:
        removed = photos.delete(session, photo_id)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such photo")
