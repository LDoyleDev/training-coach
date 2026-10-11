"""Changing today from the web (ux-flow-plan C2, C3): Rest today, Push to tomorrow, Swap and
Undo, through the same services as the bot's buttons and /undo (ADR-0022, ADR-0048). Owner-only.

Every change names the session the browser shows. When today's session is a different one now
(another device, the bot, an earlier tap), nothing changes and the answer is 409, like the
bot's "that button is out of date". Each answer carries the new today, so the page re-renders
without another request, and what Undo would take back.
"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.api.session import TodayView, today_view
from training_coach.config import Settings
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import blocks, guided, queue_actions, undo
from training_coach.services.today import position

router = APIRouter(prefix="/api/today", tags=["today"])

STALE = "today's session has changed"
REFUSED = {
    undo.NOTHING: "Nothing to undo. You can undo the last rest day, swap, push or saved log.",
    undo.TOO_OLD: "The last change was more than a day ago, so it can't be undone.",
    undo.CHANGED: "Something changed since then (another log or change), so it can't be "
    "undone safely.",
}


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _settings_and_day(request: Request) -> tuple[Settings, date]:
    settings: Settings = request.app.state.settings
    return settings, local_date(datetime.now(UTC), settings.tz)


class ChangeBody(BaseModel):
    template_id: int  # the session the browser shows: a different one now is a conflict


class PickBody(ChangeBody):
    picked_id: int


class UndoOfferView(BaseModel):
    event_id: int  # send it back to undo exactly this change
    what: str  # "the rest day for Legs"


class ChangedView(BaseModel):
    session: str  # the session rested or pushed, or the one now on for today
    advanced: bool = False  # Rest today on the optional rest session: it counts as done
    today: TodayView
    undo: UndoOfferView | None


class ChoiceView(BaseModel):
    template_id: int
    name: str


class ChoicesView(BaseModel):
    template_id: int  # the session shown today
    next: ChoiceView | None  # "Do the next one first", while today's is the planned one
    others: list[ChoiceView]  # any other session, for today only


class UndoView(BaseModel):
    """What Undo would take back, or why nothing can be."""

    offer: UndoOfferView | None
    refused: str | None


class UndoBody(BaseModel):
    event_id: int = Field(ge=1)


class UndoneView(BaseModel):
    what: str
    next_session: str | None
    today: TodayView


def _offer(session: Session) -> UndoOfferView | None:
    found = undo.last(session, datetime.now(UTC))
    if isinstance(found, undo.Blocked):
        return None
    return UndoOfferView(event_id=found.event_id, what=found.what)


def _planned(session: Session, on: date, settings: Settings, shown: int) -> int | None:
    """The queue's planned session, while today's is still the one the browser shows."""
    plan = guided.today(session, on, settings.tz)
    current = position(session)
    if plan is None or plan.template_id != shown or current is None:
        return None
    return current.pointer


def _changed(
    session: Session, on: date, settings: Settings, name: str, advanced: bool = False
) -> ChangedView:
    today = today_view(session, on, settings)
    return ChangedView(session=name, advanced=advanced, today=today, undo=_offer(session))


def _stale() -> HTTPException:
    return HTTPException(status.HTTP_409_CONFLICT, STALE)


@router.post("/rest", response_model=ChangedView)
def rest(body: ChangeBody, request: Request, user: Owner) -> ChangedView:
    """Rest today: the optional rest session counts as done, any other waits a day."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        planned = _planned(session, on, settings, body.template_id)
        outcome = queue_actions.rest_today(session, planned, on) if planned is not None else None
        if outcome is None:
            raise _stale()
        return _changed(session, on, settings, outcome.session, outcome.advanced)


@router.post("/push", response_model=ChangedView)
def push(body: ChangeBody, request: Request, user: Owner) -> ChangedView:
    """Hold today's planned session for tomorrow; the rest of the week shifts a day."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        planned = _planned(session, on, settings, body.template_id)
        name = queue_actions.push_to_tomorrow(session, planned, on) if planned is not None else None
        if name is None:
            raise _stale()
        return _changed(session, on, settings, name)


@router.get("/choices", response_model=ChoicesView)
def choices(request: Request, user: Owner) -> ChoicesView:
    """What Swap offers: the next session first, or any other one for today."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        plan = guided.today(session, on, settings.tz)
        current = position(session)
        if plan is None or current is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "nothing planned today")
        found = queue_actions.next_up(session) if current.pointer == plan.template_id else None
        others = queue_actions.choices(session)
    return ChoicesView(
        template_id=plan.template_id,
        next=ChoiceView(template_id=found[0], name=found[1]) if found else None,
        others=[ChoiceView(template_id=t, name=n) for t, n in others if t != plan.template_id],
    )


@router.post("/next", response_model=ChangedView)
def next_first(body: ChangeBody, request: Request, user: Owner) -> ChangedView:
    """Do the next session today and the planned one tomorrow (ADR-0022)."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        planned = _planned(session, on, settings, body.template_id)
        swapped = (
            queue_actions.swap_next(session, planned, blocks.current(session, on, settings.tz))
            if planned == body.template_id  # not after a pick: that session isn't the queue's
            else None
        )
        if swapped is None:
            raise _stale()
        return _changed(session, on, settings, swapped.name)


@router.post("/pick", response_model=ChangedView)
def pick(body: PickBody, request: Request, user: Owner) -> ChangedView:
    """Do another session today; the planned one is still next (ADR-0022)."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        planned = _planned(session, on, settings, body.template_id)
        block = blocks.current(session, on, settings.tz)
        picked = (
            queue_actions.pick(session, planned, body.picked_id, block)
            if planned is not None
            else None
        )
        if picked is None:
            raise _stale()
        return _changed(session, on, settings, picked.name)


@router.get("/undo", response_model=UndoView)
def undoable(request: Request, user: Owner) -> UndoView:
    """The change Undo would take back: the last rest day, push, swap or saved log."""
    with session_scope(_bound(request, user)) as session:
        found = undo.last(session, datetime.now(UTC))
    if isinstance(found, undo.Blocked):
        return UndoView(offer=None, refused=REFUSED[found.reason])
    return UndoView(offer=UndoOfferView(event_id=found.event_id, what=found.what), refused=None)


@router.post("/undo", response_model=UndoneView)
def undo_change(body: UndoBody, request: Request, user: Owner) -> UndoneView:
    """Take back the change ``event_id`` names, if it is still the last one (ADR-0048).
    409 when it isn't: a newer change, or something moved since."""
    settings, on = _settings_and_day(request)
    with session_scope(_bound(request, user)) as session:
        result = undo.apply(session, body.event_id, datetime.now(UTC))
        if isinstance(result, undo.Blocked):
            raise HTTPException(status.HTTP_409_CONFLICT, REFUSED[result.reason])
        today = today_view(session, on, settings)
    return UndoneView(what=result.what, next_session=result.next_session, today=today)
