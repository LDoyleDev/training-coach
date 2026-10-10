"""The signed-in person's sign-in methods (ADR-0036): passkeys and signed-in browsers, each
removable, so a lost phone can be cut off. Owner-only."""

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.alerts import alert
from training_coach.api.auth import COOKIE, Fresh, Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, passkeys
from training_coach.services.export import archive

router = APIRouter(prefix="/api/account", tags=["account"])
log = structlog.get_logger(__name__)


class PasskeyView(BaseModel):
    id: int
    name: str
    created_at: datetime
    last_used_at: datetime | None


class DeviceView(BaseModel):
    id: int
    label: str
    created_at: datetime
    last_seen_at: datetime
    current: bool


class SignIns(BaseModel):
    passkeys: list[PasskeyView]
    devices: list[DeviceView]


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


@router.get("/sign-ins", response_model=SignIns)
def sign_ins(request: Request, user: Owner) -> SignIns:
    token = request.cookies.get(COOKIE, "")
    with session_scope(_bound(request, user)) as session:
        keys = passkeys.keys(session)
        devices = auth.devices(session, token, datetime.now(UTC))
    return SignIns(
        passkeys=[PasskeyView(**vars(k)) for k in keys],
        devices=[DeviceView(**vars(d)) for d in devices],
    )


@router.delete("/passkeys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_passkey(
    key_id: int, request: Request, background: BackgroundTasks, user: Owner, _fresh: Fresh
) -> None:
    """Remove a passkey; like adding one, it needs a recent sign-in (ADR-0040)."""
    with session_scope(_bound(request, user)) as session:
        current = request.cookies.get(COOKIE, "")
        removed = passkeys.remove(session, key_id, datetime.now(UTC), current)
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such passkey")
    alert(request, background, "passkey_removed", "A passkey was removed from Training Coach.")


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def sign_out_device(
    device_id: int, request: Request, background: BackgroundTasks, user: Owner
) -> None:
    with session_scope(_bound(request, user)) as session:
        ended = auth.end_device(session, device_id, datetime.now(UTC))
    if not ended:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such signed-in device")
    alert(request, background, "device_signed_out", "A device was signed out of Training Coach.")


@router.get(
    "/export", response_class=Response, responses={200: {"content": {"application/zip": {}}}}
)
def export(request: Request, user: Owner) -> Response:
    """Everything stored about the signed-in person, as a zip: data.json and the photos."""
    now = datetime.now(UTC)
    with session_scope(_bound(request, user)) as session:
        data = archive(session, now)
    log.info("account.exported", bytes=len(data))
    name = f"training-coach-{now.date().isoformat()}.zip"
    return Response(
        data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "private, no-store",
        },
    )
