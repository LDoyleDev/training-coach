"""Consent per category (ADR-0090): giving it, withdrawing it, and erasing a category's data when
it's withdrawn. Callers pass a session bound to the person (ADR-0029). The owner is never asked:
their categories are always open."""

from datetime import datetime

import structlog
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from training_coach.db.base import Base
from training_coach.db.models import (
    AiComment,
    AiConnection,
    BandFeed,
    Consent,
    DailyCheck,
    Event,
    HealthDay,
    HeartRateSample,
    ImportedWorkout,
    IngestKey,
    LogProposal,
    Measurement,
    ProgressPhoto,
    SleepSession,
    UserSettings,
    Workout,
)
from training_coach.db.session import ALL_USERS
from training_coach.domain.consent import VERSIONS, Answer, Category, Entry, is_open, latest
from training_coach.domain.measurements import BodyFatEstimate
from training_coach.services.users import OWNER

log = structlog.get_logger(__name__)

DEFAULT_THIGH_OFFSET_CM = 15  # the column's default (models.UserSettings)
# proposals.BODY and proposals.CARDIO: that module asks this one, so it can't be imported here.
BODY, CARDIO = "body", "cardio"


def answers(session: Session) -> dict[Category, Entry]:
    """The person's current answer per category; a category never asked is missing."""
    rows = session.scalars(select(Consent).order_by(Consent.id)).all()
    return latest([Entry(Category(r.category), Answer(r.answer), r.version, r.at) for r in rows])


def open_to(session: Session, user_id: int) -> frozenset[Category]:
    """The categories ``user_id`` may keep and see: all of them for the owner, and for a member
    those they've said yes to at the wording shown now. Works in any session, bound or not:
    the token check and the phone's posts read it before they know whose session to open."""
    if user_id == OWNER:
        return frozenset(Category)
    rows = session.scalars(
        select(Consent).where(Consent.user_id == user_id).order_by(Consent.id),
        execution_options={ALL_USERS: True},
    ).all()
    found = latest([Entry(Category(r.category), Answer(r.answer), r.version, r.at) for r in rows])
    return frozenset(c for c in Category if is_open(found.get(c)))


def opened(session: Session, user_id: int, category: Category) -> bool:
    """Whether ``user_id`` may keep and see ``category``."""
    return category in open_to(session, user_id)


def give(session: Session, category: Category, now: datetime) -> None:
    """Record a yes to the current wording."""
    _record(session, category, Answer.GIVEN, now)
    log.info("consent.given", category=category.value)


def withdraw(session: Session, category: Category, now: datetime) -> None:
    """Record the withdrawal and erase what the category kept. The plan and training stay."""
    _record(session, category, Answer.WITHDRAWN, now)
    _erase(session, category)
    session.flush()
    log.info("consent.withdrawn", category=category.value)


def _record(session: Session, category: Category, answer: Answer, now: datetime) -> None:
    session.add(
        Consent(category=category.value, answer=answer.value, version=VERSIONS[category], at=now)
    )
    kind = "consent.given" if answer is Answer.GIVEN else "consent.withdrawn"
    session.add(Event(kind=kind, payload={"category": category.value}))
    session.flush()


def _erase(session: Session, category: Category) -> None:
    if category is Category.BODY:
        session.execute(delete(Measurement))
        session.execute(delete(ProgressPhoto))
        for found in session.scalars(select(UserSettings)):
            found.height_cm = None
            found.thigh_offset_cm = DEFAULT_THIGH_OFFSET_CM
            found.body_fat_estimate = BodyFatEstimate.OFF.value
        _no_ai_sight(session, body=True)
        _drop_proposals(session, BODY)
    elif category is Category.DAILY_CHECK:
        session.execute(delete(DailyCheck))
        _no_ai_sight(session, body=False)
    elif category is Category.BAND:
        band: tuple[type[Base], ...] = (
            HeartRateSample,
            SleepSession,
            HealthDay,
            ImportedWorkout,
            BandFeed,
        )
        for model in band:
            session.execute(delete(model))
        session.execute(delete(IngestKey))  # the phone's key: its posts are refused from now on
        for workout in session.scalars(
            select(Workout).where((Workout.avg_hr.is_not(None)) | (Workout.max_hr.is_not(None)))
        ):
            workout.avg_hr = workout.max_hr = None
        for found in session.scalars(select(UserSettings)):
            found.max_hr = None
        _drop_proposals(session, CARDIO)
    # The walk-through's answers are kept by the walk-through, which erases its own (ADR-0090).


def _no_ai_sight(session: Session, *, body: bool) -> None:
    """The AI comment stops seeing the category, and comments that may have mentioned it go."""
    for connection in session.scalars(select(AiConnection)):
        if body:
            connection.share_body = False
        else:
            connection.share_readiness = False
    session.execute(delete(AiComment))


def _drop_proposals(session: Session, kind: str) -> None:
    """Proposals an AI app made of this kind, waiting, saved or discarded: a body one, or a
    cardio one that may carry heart rate, as their payload and summary hold the values. A saved
    log itself is in its own table and stays as training data (review of #617)."""
    session.execute(delete(LogProposal).where(LogProposal.kind == kind))
