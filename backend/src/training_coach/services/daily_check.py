"""The daily check (ADR-0053): reading a day's answers and saving them, for the web app and the
bot alike. Callers pass a session bound to the user (ADR-0029). Health data: never logged."""

from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from training_coach.db.models import DailyCheck
from training_coach.domain.daily_check import Answers, Energy, Sleep, Soreness

KEEP = timedelta(days=365)  # older answers are deleted as new ones come in


def on(session: Session, day: date) -> Answers | None:
    """The answers for ``day``, or None when not answered."""
    row = session.scalar(select(DailyCheck).where(DailyCheck.local_date == day))
    if row is None:
        return None
    return Answers(Sleep(row.sleep), Soreness(row.soreness), Energy(row.energy))


def save(session: Session, day: date, answers: Answers, now: datetime) -> None:
    """Store ``day``'s answers, replacing any given earlier that day, and drop the ones past
    keeping."""
    row = session.scalar(select(DailyCheck).where(DailyCheck.local_date == day))
    if row is None:
        row = DailyCheck(local_date=day)
        session.add(row)
    row.sleep, row.soreness, row.energy = answers.sleep, answers.soreness, answers.energy
    row.answered_at = now
    session.execute(delete(DailyCheck).where(DailyCheck.local_date < day - KEEP))
    session.flush()
