"""People (ADR-0059): an admin's invites and members, and joining with an invite.

Everything here answers 404 while ``TC_MULTI_USER`` is off, so nothing opens before the notice,
consent and DPIA are ready. The admin routes hold counts, labels, join days and open invites
only. ``/api/join`` is public: the invite's token is what proves it, rate limited per address.
"""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.alerts import alert, alert_chat
from training_coach.api.auth import Admin, Fresh, set_session_cookie
from training_coach.api.oauth import limited
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.services import invites, left_list, users
from training_coach.services.erase import leave

router = APIRouter(prefix="/api", tags=["people"])


class InviteBody(BaseModel):
    label: str | None = Field(default=None, max_length=40)  # what the list calls them: "Mum"


class MadeView(BaseModel):
    token: str  # shown once: the link is /join#<token>
    expires_at: datetime


class InviteView(BaseModel):
    id: int
    label: str | None
    created_at: datetime
    expires_at: datetime


class MemberView(BaseModel):
    id: int  # to remove them by; says nothing about them
    label: str | None
    joined: date


class PeopleView(BaseModel):
    members: list[MemberView]
    invites: list[InviteView]  # open ones
    max_members: int


class RemoveBody(BaseModel):
    confirm: Literal["remove"]  # typed by the admin: no removing someone by a stray click


class JoinBody(BaseModel):
    token: str = Field(max_length=100)
    adult: bool  # they said they are 18 or over


def _on(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    if not settings.multi_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "invites are off")
    return settings


def _shared(request: Request) -> sessionmaker[Session]:
    sessions: sessionmaker[Session] = request.app.state.shared_sessions
    return sessions


@router.get("/people", response_model=PeopleView)
def get_people(request: Request, user: Admin) -> PeopleView:
    """Members' labels and join days, and the open invites: nothing of anyone's data."""
    settings = _on(request)
    with session_scope(_shared(request)) as session:
        found = invites.members(session)
        open_ = invites.open_invites(session, datetime.now(UTC))
    return PeopleView(
        members=[
            MemberView(id=m.user_id, label=m.label, joined=m.joined.astimezone(settings.tz).date())
            for m in found
        ],
        invites=[InviteView(**vars(i)) for i in open_],
        max_members=settings.max_members,
    )


@router.post("/invites", response_model=MadeView, status_code=status.HTTP_201_CREATED)
def make_invite(body: InviteBody, request: Request, user: Admin) -> MadeView:
    """A one-time link for someone to join, valid 72 hours; 409 when the house is full (open
    invites count)."""
    settings = _on(request)
    now = datetime.now(UTC)
    with session_scope(_shared(request)) as session:
        token = invites.make(session, user, (body.label or "").strip(), now, settings.max_members)
    if token is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "no room for another member")
    return MadeView(token=token, expires_at=now + invites.INVITE_TTL)


@router.delete("/invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invite(invite_id: int, request: Request, user: Admin) -> None:
    """Revoke an open invite; 404 for one that's used, expired, revoked or unknown."""
    _on(request)
    with session_scope(_shared(request)) as session:
        done = invites.revoke(session, invite_id, datetime.now(UTC))
    if not done:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no open invite")


@router.post("/people/{member_id}/remove", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    member_id: int,
    body: RemoveBody,
    request: Request,
    background: BackgroundTasks,
    user: Admin,
    _fresh: Fresh,
) -> None:
    """Remove a member (ADR-0059, ADR-0088), once the admin has told them and offered their
    export: everything of theirs is deleted, as if they had left. 404 for anyone who isn't a
    member (an admin can't be removed). Needs a recent sign-in and the word typed."""
    settings = _on(request)
    with session_scope(_shared(request)) as session:
        chat = users.telegram_chat(session, member_id)  # now: afterwards there is no one to ask
        gone = leave(
            session, member_id, left_list.for_url(settings.database_url), datetime.now(UTC)
        )
    if not gone:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such member")
    alert_chat(
        request,
        background,
        chat,
        "member_removed",
        "The admin removed you from Training Coach, and everything of yours was deleted. "
        "Backups age out within 5 weeks.",
    )


@router.post("/join", status_code=status.HTTP_204_NO_CONTENT)
def join(body: JoinBody, request: Request, response: Response, background: BackgroundTasks) -> None:
    """Join with an invite: the new member signed in, to add a passkey next. 401 for a link that
    is used, revoked or expired; 422 unless they are an adult; 409 when there's no room."""
    settings = _on(request)
    limited(request, "join")
    if not body.adult:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "for adults only")
    device = request.headers.get("user-agent", "")
    with session_scope(_shared(request)) as session:
        joined = invites.redeem(
            session, body.token, datetime.now(UTC), device, settings.max_members
        )
    if joined is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "this invite has expired or was used")
    if not isinstance(joined, invites.Joined):
        raise HTTPException(status.HTTP_409_CONFLICT, "no room for another member")
    set_session_cookie(response, joined.cookie)
    who = joined.label or "Someone"
    alert(
        request,
        background,
        joined.invited_by,
        "invite_used",
        f"{who} joined Training Coach with your invite.",
    )
