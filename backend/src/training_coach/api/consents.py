"""Consent per category for the web app (ADR-0090): what the person has said yes to, giving it,
and withdrawing it, which erases that category's data. The owner isn't asked: it's their own
data, so their categories are always open and these answer them 409."""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Fresh, Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.consent import VERSIONS, Answer, Category, is_open
from training_coach.services import consent
from training_coach.services.users import OWNER

router = APIRouter(prefix="/api/consents", tags=["consents"])

OWN_DATA = "your own data needs no consent"


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


class CategoryView(BaseModel):
    category: Category
    version: int  # the wording shown now (frontend/src/consent/wording.ts)
    open: bool
    answer: Answer | None  # the latest, whatever wording it was to; None if never asked
    at: datetime | None


class ConsentsView(BaseModel):
    asked: bool  # false for the owner
    categories: list[CategoryView]


def _view(request: Request, user: int) -> ConsentsView:
    with session_scope(_bound(request, user)) as session:
        found = consent.answers(session)
    owner = user == OWNER
    return ConsentsView(
        asked=not owner,
        categories=[
            CategoryView(
                category=category,
                version=VERSIONS[category],
                open=owner or is_open(entry),
                answer=entry.answer if entry else None,
                at=entry.at if entry else None,
            )
            for category in Category
            for entry in [found.get(category)]
        ],
    )


@router.get("", response_model=ConsentsView)
def get_consents(request: Request, user: Owner) -> ConsentsView:
    return _view(request, user)


class GiveBody(BaseModel):
    version: int  # the wording the browser showed


@router.put("/{category}", response_model=ConsentsView)
def give(category: Category, body: GiveBody, request: Request, user: Owner) -> ConsentsView:
    """A yes to the wording shown. 409 if the browser showed an older one (a page loaded before
    a release): it reloads and shows the new wording."""
    if user == OWNER:
        raise HTTPException(status.HTTP_409_CONFLICT, OWN_DATA)
    if body.version != VERSIONS[category]:
        raise HTTPException(status.HTTP_409_CONFLICT, "the wording changed: reload the page")
    with session_scope(_bound(request, user)) as session:
        consent.give(session, category, datetime.now(UTC))
    return _view(request, user)


@router.delete("/{category}", response_model=ConsentsView)
def withdraw(category: Category, request: Request, user: Owner, _fresh: Fresh) -> ConsentsView:
    """Withdraw, and erase what the category kept. A recent sign-in, as it deletes data."""
    if user == OWNER:
        raise HTTPException(status.HTTP_409_CONFLICT, OWN_DATA)
    with session_scope(_bound(request, user)) as session:
        consent.withdraw(session, category, datetime.now(UTC))
    return _view(request, user)
