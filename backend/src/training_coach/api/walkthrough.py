"""The walk-through for new people (ADR-0092): what it asks (``GET /api/walkthrough``), the plan
the person's choices would make (``POST /api/walkthrough/preview``, saving nothing) and the one
Save (``POST /api/walkthrough``). The browser works out the suggested level and walks the
ladders itself; the server gets the outcomes, and the answers only with ``walkthrough`` consent.
The answers are health data: they are never logged."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from training_coach.api.auth import Owner
from training_coach.api.coverage import CoverageView, coverage_view
from training_coach.api.equipment import KitItemBody
from training_coach.api.readiness import ReadinessView, readiness_view
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.consent import Category
from training_coach.domain.enums import Place, Places
from training_coach.domain.kit import MAX_ITEMS, Item
from training_coach.domain.queue import local_date
from training_coach.domain.step_levels import Mark
from training_coach.domain.walkthrough import AgeBand, Answers, CanDo, Effort, HowLong, Often
from training_coach.services import consent, plan_edit, readiness, users, walkthrough
from training_coach.services import walkthrough_preview as views
from training_coach.services.coverage import CountedAt
from training_coach.services.seed import bundled_plan
from training_coach.services.walkthrough import Setup

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/walkthrough", tags=["walkthrough"])

LADDERS = 13  # the starters' exercises, the tibialis raise among them
MOST_ASKED = 12  # answers on one ladder: more than its steps (the longest has 11)
Avoidable = Literal["floor", "kneeling", "impact", "hanging", "knees"]
Slug = Annotated[str, Field(max_length=64)]


def _bound(request: Request, user: int) -> sessionmaker[Session]:
    return make_session_factory(request.app.state.engine, user_id=user)


def _today(request: Request) -> date:
    return local_date(datetime.now(UTC), request.app.state.settings.tz)


# ------------------------------------------------------------------------------- GET


class WalkthroughStepView(BaseModel):
    id: int
    position: int  # 0 is the bottom, where anyone starts: it has no question
    name: str  # with the ladder's slug, the web's figure for the step (figureFor)
    level: int | None  # who it is for, 1-6 (ADR-0083)
    question: str | None  # "Can you do ...?"
    cue: str | None
    needs: list[str]  # the catalogue's: "kettlebell:8", "pull-up bar"; the lock rule's input
    marks: list[str]  # "floor", "kneeling", "impact", "hanging", "knees", "balance"


class WalkthroughLadderView(BaseModel):
    slug: str
    name: str
    on: int | None  # the step id the person is on now
    steps: list[WalkthroughStepView]  # easiest first


class StarterItemView(BaseModel):
    exercise: str  # slug
    name: str
    sets: int
    rep_min: int
    rep_max: int
    per_side: bool
    pair: int | None


class StarterSessionView(BaseModel):
    slug: str
    name: str
    focus: str
    rest_after: int  # rest days after it (ADR-0091)
    items: list[StarterItemView]  # in the trim's order


class StarterView(BaseModel):
    slug: str
    name: str
    days: int
    sessions: list[StarterSessionView]  # queue order


class WalkthroughView(BaseModel):
    who: views.Who
    revision: str  # the plan's now: Save sends it back
    consent_open: bool  # the answers may be sent with Save
    ladders: list[WalkthroughLadderView]  # in the order they are asked
    starters: list[StarterView]
    readiness: ReadinessView  # as GET /api/readiness
    country: str | None  # where they live; None: ask (ADR-0085)


@router.get("", response_model=WalkthroughView)
def get_walkthrough(request: Request, user: Owner) -> WalkthroughView:
    plan = bundled_plan()
    names = {e.slug: e.name for e in plan.exercises}
    with session_scope(_bound(request, user)) as session:
        who = views.who(session)
        ladders = views.ladders(session, plan)
        row = readiness.latest(session)
        version, answered = (row.version, row.answered_at) if row is not None else (None, None)
        found = WalkthroughView(
            who=who,
            revision=plan_edit.revision(session),
            consent_open=consent.opened(session, user, Category.WALKTHROUGH),
            ladders=[
                WalkthroughLadderView(
                    slug=ladder.slug,
                    name=ladder.name,
                    on=ladder.on,
                    steps=[
                        WalkthroughStepView(
                            id=s.id,
                            position=s.position,
                            name=s.name,
                            level=s.level,
                            question=s.question,
                            cue=s.cue,
                            needs=list(s.needs),
                            marks=list(s.marks),
                        )
                        for s in ladder.steps
                    ],
                )
                for ladder in ladders
            ],
            starters=[
                StarterView(
                    slug=st.slug,
                    name=st.name,
                    days=st.days,
                    sessions=[
                        StarterSessionView(
                            slug=s.slug,
                            name=s.name,
                            focus=s.focus,
                            rest_after=s.rest_after,
                            items=[
                                StarterItemView(name=names[i.exercise], **i.model_dump())
                                for i in s.items
                            ],
                        )
                        for s in st.sessions
                    ],
                )
                for st in plan.starters
            ],
            readiness=readiness_view(version, answered, datetime.now(UTC)),
            country=users.country(session),
        )
    return found


# ------------------------------------------------------------------------- the outcomes


class Outcomes(BaseModel):
    """What the person chose, as Save sends it: no answers."""

    starter: Slug
    steps: dict[Slug, int] = Field(max_length=LADDERS)  # exercise slug -> ladder step id
    starts_on: date
    places: Places = Places.HOME
    kit: list[KitItemBody] | None = Field(default=None, max_length=MAX_ITEMS)  # None: as it is
    avoid: list[Avoidable] = Field(default_factory=list, max_length=5)
    session_minutes: Literal[40, 30, 20] | None = None  # None: as planned
    session_exercises: Literal[4, 6, 8] | None = None
    left_out: list[Slug] = Field(default_factory=list, max_length=LADDERS)


class Asked(BaseModel):
    step: int  # the ladder step id asked
    answer: CanDo


class AnswersBody(BaseModel):
    """The walk-through's answers (ADR-0090 addendum): sent only with consent. Any can be empty."""

    age_band: AgeBand | None = None
    often: Often | None = None
    effort: Effort | None = None
    how_long: HowLong | None = None
    chair: bool | None = None
    stairs: bool | None = None
    walk: bool | None = None
    floor: bool | None = None
    weekdays: list[Annotated[int, Field(ge=0, le=6)]] = Field(default_factory=list, max_length=7)
    placement: dict[Slug, Annotated[list[Asked], Field(max_length=MOST_ASKED)]] = Field(
        default_factory=dict, max_length=LADDERS
    )


class WalkthroughSaveBody(Outcomes):
    revision: str = Field(max_length=64)  # GET's, so a stale tab can't overwrite
    answers: AnswersBody | None = None


def _setup(body: Outcomes, answers: Answers | None = None) -> Setup:
    return Setup(
        starter=body.starter,
        steps=dict(body.steps),
        starts_on=body.starts_on,
        places=body.places,
        kit=None
        if body.kit is None
        else [Item(i.kit, i.kg, i.min_kg, i.resistance, i.note.strip()) for i in body.kit],
        avoid=frozenset(Mark(m) for m in body.avoid),
        minutes=body.session_minutes,
        exercises=body.session_exercises,
        left_out=frozenset(body.left_out),
        answers=answers,
    )


def _answers(body: AnswersBody) -> Answers:
    try:
        return Answers(
            age_band=body.age_band,
            often=body.often,
            effort=body.effort,
            how_long=body.how_long,
            chair=body.chair,
            stairs=body.stairs,
            walk=body.walk,
            floor=body.floor,
            weekdays=tuple(body.weekdays),
            placement={
                slug: tuple((a.step, a.answer) for a in asked)
                for slug, asked in body.placement.items()
            },
        )
    except ValueError as error:  # a weekday tapped twice; never echoed with the answers
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None


# ------------------------------------------------------------------------------- preview


class FittedItemView(BaseModel):
    exercise: str  # slug
    name: str
    step: str  # the step it is done at
    sets: int  # as planned
    kept: int  # after the trim; 0: dropped
    rep_min: int
    rep_max: int
    per_side: bool
    pair: int | None


class FittedView(BaseModel):
    place: Place
    items: list[FittedItemView]
    minutes: int  # about how long, warm-up included
    fits: bool  # within the minutes per session
    dropped: list[str]  # exercises the trim drops, in the order they go


class FittedSessionView(BaseModel):
    slug: str
    name: str
    focus: str
    rest_after: int
    on: date  # the day it first lands
    home: FittedView
    gym: FittedView | None  # None: done the same way at the gym, or not trained there


class WeekDayView(BaseModel):
    date: date
    session: str | None  # its slug; None: a rest day


class PreviewView(BaseModel):
    sessions: list[FittedSessionView]  # queue order
    week: list[WeekDayView]  # seven days from the start
    coverage: list[CoverageView]  # home, or gym, or both in that order at both


def _fitted(found: views.Fitted) -> FittedView:
    return FittedView(
        place=found.place,
        items=[FittedItemView(**vars(i)) for i in found.items],
        minutes=found.minutes,
        fits=found.fits,
        dropped=list(found.dropped),
    )


@router.post("/preview", response_model=PreviewView)
def post_preview(request: Request, user: Owner, body: Outcomes) -> PreviewView:
    """The plan these choices would make, for the last screen; it saves nothing, so the owner's
    try-out gets it too. What can't be saved (a locked step, say) is refused with the reason."""
    with session_scope(_bound(request, user)) as session:
        found = views.preview(session, bundled_plan(), _setup(body), _today(request))
    if isinstance(found, str):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, found)
    counted = CountedAt(body.session_minutes, body.session_exercises)  # as its preview trims
    return PreviewView(
        sessions=[
            FittedSessionView(
                slug=s.slug,
                name=s.name,
                focus=s.focus,
                rest_after=s.rest_after,
                on=s.on,
                home=_fitted(s.home),
                gym=_fitted(s.gym) if s.gym is not None else None,
            )
            for s in found.sessions
        ],
        week=[WeekDayView(date=day, session=slug) for day, slug in found.week],
        coverage=[coverage_view(c, place, body.places, counted) for place, c in found.coverage],
    )


# ---------------------------------------------------------------------------------- save


class WalkthroughSavedView(BaseModel):
    revision: str
    kept: bool  # the answers were kept: sent, and consent still open
    starts_on: date
    moved: list[str]  # exercises placed off the step they were on


@router.post("", response_model=WalkthroughSavedView)
def post_walkthrough(
    request: Request, user: Owner, body: WalkthroughSaveBody
) -> WalkthroughSavedView:
    """Save the plan in one go (``walkthrough.apply``). The owner's plan isn't made here: 403.
    Answers without consent: 403 ``consent_needed``. A workout logged, a session in progress or a
    plan changed since: 409. What can't be saved: 422 with the reason."""
    if user == users.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "a try-out: the owner's plan stays as it is")
    answers = _answers(body.answers) if body.answers is not None else None
    with session_scope(_bound(request, user)) as session:
        if answers is not None and not consent.opened(session, user, Category.WALKTHROUGH):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, {"consent_needed": Category.WALKTHROUGH.value}
            )
        saved = walkthrough.apply(
            session,
            bundled_plan(),
            _setup(body, answers),
            body.revision,
            _today(request),
            datetime.now(UTC),
        )
        if isinstance(saved, str):
            session.rollback()  # nothing was written, but say so plainly
    if saved in (walkthrough.CLOSED, walkthrough.IN_PROGRESS, walkthrough.STALE):
        raise HTTPException(status.HTTP_409_CONFLICT, saved)
    if isinstance(saved, str):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, saved)
    log.info("api.walkthrough_saved", kept=saved.kept, moved=len(saved.moved))
    return WalkthroughSavedView(
        revision=saved.revision, kept=saved.kept, starts_on=body.starts_on, moved=list(saved.moved)
    )
