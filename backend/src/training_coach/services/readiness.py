"""The readiness questions' answers (ADR-0046): reading the latest and saving new ones.
Health data: the answers are never logged."""

from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import ReadinessAnswers
from training_coach.domain.readiness import KEYS, VERSION, Status, status


def latest(session: Session) -> ReadinessAnswers | None:
    return session.scalar(select(ReadinessAnswers))


def current(session: Session, now: datetime) -> Status:
    row = latest(session)
    if row is None:
        return Status.DUE
    return status(row.answers, row.version, row.answered_at, now)


def save(session: Session, answers: Mapping[str, bool], now: datetime) -> Status:
    """Store a full set of answers to the current questions, replacing any earlier ones."""
    if set(answers) != KEYS:
        raise ValueError("every question needs an answer")
    row = latest(session)
    if row is None:
        row = ReadinessAnswers()
        session.add(row)
    row.version, row.answers, row.answered_at = VERSION, dict(answers), now
    session.flush()
    return status(row.answers, row.version, row.answered_at, now)
