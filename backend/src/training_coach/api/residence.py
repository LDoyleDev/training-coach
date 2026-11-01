"""Where the person lives, on Account (ADR-0085 layer 3): a country from the EU and EEA list.
"Somewhere else" is refused: the service is for people living there. Owner-only.

There's no sign-up yet (ADR-0059's invites aren't built); the setup flow asks it when it comes
(program-builder.md, step 10)."""

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from training_coach.api.auth import Owner
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.region import ALLOWED
from training_coach.services import users

router = APIRouter(prefix="/api/account/residence", tags=["account"])
ELSEWHERE = (
    "Training Coach is only for people living in the EU or EEA, so we can't offer it to you."
)


class ResidenceView(BaseModel):
    country: str | None  # ISO 3166-1 alpha-2, or None until given
    choices: list[str]  # every code on the list


class ResidenceBody(BaseModel):
    country: str = Field(min_length=2, max_length=2)


def _view(country: str | None) -> ResidenceView:
    return ResidenceView(country=country, choices=sorted(ALLOWED))


@router.get("", response_model=ResidenceView)
def get_residence(request: Request, user: Owner) -> ResidenceView:
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        return _view(users.country(session, user))


@router.put("", response_model=ResidenceView)
def set_residence(body: ResidenceBody, request: Request, user: Owner) -> ResidenceView:
    """Save the country; one off the list gets 422 with the reason."""
    with session_scope(make_session_factory(request.app.state.engine, user_id=user)) as session:
        if not users.set_country(session, user, body.country):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, ELSEWHERE)
        return _view(users.country(session, user))
