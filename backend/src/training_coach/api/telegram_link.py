"""A member's Telegram on Account (ADR-0089): connect it with a link and the code the bot
sends, or disconnect it. The owner's Telegram is set on the server
(``TC_TELEGRAM_ALLOWED_USER_ID``), so the owner only sees that. With ``TC_MULTI_USER`` off a
member gets 403 here, as everywhere (``api.auth.owner``)."""

from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.alerts import alert_chat, forget, reschedule
from training_coach.api.auth import Fresh, Owner
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import telegram_link, users

router = APIRouter(prefix="/api/account/telegram", tags=["account"])

# Each refusal as the status and detail the web app shows.
REFUSED = {
    telegram_link.NO_LINK: (status.HTTP_404_NOT_FOUND, "no open link: make a new one"),
    telegram_link.SHARED: (status.HTTP_409_CONFLICT, "someone else used this link too"),
    telegram_link.WRONG: (status.HTTP_400_BAD_REQUEST, "that's not the code"),
    telegram_link.ENDED: (status.HTTP_410_GONE, "too many wrong codes: make a new link"),
    telegram_link.TAKEN: (status.HTTP_409_CONFLICT, "that Telegram account is already in use"),
    telegram_link.ALREADY: (status.HTTP_409_CONFLICT, "your Telegram is connected already"),
}
CONNECTED = "Connected. Training Coach will message you here."
DISCONNECTED = (
    "This Telegram account was disconnected from Training Coach. Not you? Sign in on the "
    "website and check your Account page."
)


class TelegramPending(BaseModel):
    expires_at: datetime
    claims: int  # how many opened the link in Telegram: more than one means it leaked


class TelegramView(BaseModel):
    set_on_server: bool  # the owner's: no connecting or disconnecting here
    connected: bool
    name: str | None  # the Telegram first name when they connected
    since: datetime | None
    pending: TelegramPending | None


class TelegramLinkView(BaseModel):
    url: str  # t.me/<bot>?start=<token>, shown once
    expires_at: datetime


class TelegramCode(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class TelegramMatch(BaseModel):
    name: str


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _member(user: int) -> None:
    if user == users.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "the owner's Telegram is set on the server")


def _configured(request: Request) -> int | None:
    settings: Settings = request.app.state.settings
    return settings.telegram_allowed_user_id


@router.get("", response_model=TelegramView)
def telegram(request: Request, user: Owner) -> TelegramView:
    with session_scope(_bound(request, user)) as session:
        found = telegram_link.status(session, user, datetime.now(UTC))
    pending = found.pending
    return TelegramView(
        set_on_server=user == users.OWNER,
        connected=found.connected,
        name=found.name,
        since=found.since,
        pending=TelegramPending(**vars(pending)) if pending is not None else None,
    )


@router.post("/link", response_model=TelegramLinkView)
def make_link(request: Request, user: Owner, _fresh: Fresh) -> TelegramLinkView:
    """A new connect link, which ends any earlier one. Needs a recent sign-in."""
    _member(user)
    bot: str | None = getattr(request.app.state, "bot_username", None)
    if bot is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "the Telegram bot is off")
    now = datetime.now(UTC)
    with session_scope(_bound(request, user)) as session:
        if telegram_link.status(session, user, now).connected:
            raise HTTPException(status.HTTP_409_CONFLICT, "your Telegram is connected already")
        token = telegram_link.make(session, now)
    url = f"https://t.me/{bot}?start={token}"
    return TelegramLinkView(url=url, expires_at=now + telegram_link.LINK_TTL)


@router.delete("/link", status_code=status.HTTP_204_NO_CONTENT)
def cancel_link(request: Request, user: Owner) -> None:
    """End the open link, if any: it only takes something away."""
    _member(user)
    with session_scope(_bound(request, user)) as session:
        telegram_link.cancel(session)


@router.post("/code", response_model=TelegramMatch)
def check_code(body: TelegramCode, request: Request, user: Owner) -> TelegramMatch:
    """The Telegram name a code was sent to, shown before Confirm. A wrong one counts."""
    _member(user)
    with session_scope(_bound(request, user)) as session:
        found = telegram_link.check(session, body.code, datetime.now(UTC))
    if not isinstance(found, telegram_link.Match):
        raise HTTPException(*REFUSED[found])
    return TelegramMatch(name=found.name)


@router.post("/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm(
    body: TelegramCode, request: Request, background: BackgroundTasks, user: Owner, _fresh: Fresh
) -> None:
    """Connect the Telegram account the code was sent to. Needs a recent sign-in."""
    _member(user)
    try:
        with session_scope(_bound(request, user)) as session:
            done = telegram_link.confirm(
                session, user, body.code, datetime.now(UTC), _configured(request)
            )
    except IntegrityError:  # someone else connected that account in the same moment
        done = telegram_link.TAKEN
    if not isinstance(done, telegram_link.Linked):
        raise HTTPException(*REFUSED[done])
    reschedule(request, user)  # their morning, nudge and review start (step 9)
    alert_chat(request, background, done.chat, "telegram_linked", CONNECTED)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def unlink(request: Request, background: BackgroundTasks, user: Owner) -> None:
    """Disconnect Telegram, telling the chat it was. No recent sign-in needed: it only takes
    access away."""
    _member(user)
    with session_scope(_bound(request, user)) as session:
        chat = telegram_link.unlink(session, user, datetime.now(UTC))
    if chat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no Telegram connected")
    forget(request, user)  # what the bot kept for that chat (ADR-0089)
    alert_chat(request, background, chat, "telegram_unlinked", DISCONNECTED)
