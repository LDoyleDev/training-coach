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
from training_coach.domain.consent import VERSIONS, Answer, Category, Entry, is_open, latest
from training_coach.domain.measurements import BodyFatEstimate
from training_coach.services.proposals import BODY, CARDIO
from training_coach.services.users import OWNER

log = structlog.get_logger(__name__)

DEFAULT_THIGH_OFFSET_CM = 15  # the column's default (models.UserSettings)


def answers(session: Session) -> dict[Category, Entry]:
    """The person's current answer per category; a category never asked is missing."""
    rows = session.scalars(select(Consent).order_by(Consent.id)).all()
    return latest([Entry(Category(r.category), Answer(r.answer), r.version, r.at) for r in rows])


def opened(session: Session, user_id: int, category: Category) -> bool:
    """Whether ``user_id`` may keep and see ``category``: the owner always, a member once they've
    said yes to the wording shown now."""
    return user_id == OWNER or is_open(answers(session).get(category))


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
    """Waiting proposals an AI app made of this kind: a body one, or a cardio one that may carry
    heart rate. Saved logs are training data and stay."""
    session.execute(
        delete(LogProposal).where(LogProposal.kind == kind, LogProposal.status == "pending")
    )
