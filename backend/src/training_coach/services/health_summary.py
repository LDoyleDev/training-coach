"""What the band says about the last day or so (ADR-0054): last night's sleep, steps and
resting heart rate, for Home, Progress, the daily check and the morning message. Reads only;
the caller passes a session bound to the person. Health data: never logged."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import HealthDay, SleepSession
from training_coach.domain import health
from training_coach.domain.daily_check import Sleep
from training_coach.services import zones

RECENT = timedelta(days=3)  # a resting heart rate older than this isn't shown


@dataclass(frozen=True)
class Night:
    start: datetime
    end: datetime
    asleep: int  # minutes
    awake: int
    light: int
    deep: int
    rem: int


@dataclass(frozen=True)
class Summary:
    sleep: Night | None  # last night: the longest sleep that ended today
    steps_today: int | None
    steps_yesterday: int | None
    resting: int | None  # the latest resting heart rate, from the last 3 days
    usual_resting: int | None  # the median of the last 7 nights, when there are any


def last_night(session: Session, today: date) -> Night | None:
    rows = session.scalars(select(SleepSession).where(SleepSession.local_date == today))
    found = max(rows, key=lambda s: s.end_at - s.start_at, default=None)
    if found is None:
        return None
    return Night(
        found.start_at,
        found.end_at,
        found.asleep_min,
        found.awake_min,
        found.light_min,
        found.deep_min,
        found.rem_min,
    )


def suggested_sleep(session: Session, today: date) -> tuple[Sleep, int] | None:
    """The daily check's sleep answer last night suggests, and the minutes asleep."""
    night = last_night(session, today)
    return (health.sleep_answer(night.asleep), night.asleep) if night is not None else None


def summary(session: Session, today: date) -> Summary:
    days = {
        d.local_date: d
        for d in session.scalars(
            select(HealthDay).where(
                HealthDay.local_date >= today - RECENT, HealthDay.local_date <= today
            )
        )
    }
    yesterday = days.get(today - timedelta(days=1))
    resting = next(
        (days[d].resting_hr for d in sorted(days, reverse=True) if days[d].resting_hr), None
    )
    usual = zones.current(session, today).zones.rest if resting is not None else None
    return Summary(
        last_night(session, today),
        days[today].steps if today in days else None,
        yesterday.steps if yesterday is not None else None,
        resting,
        usual,
    )


def morning_line(session: Session, today: date) -> str | None:
    """The morning message's line, e.g. "Your band: 7 h 20 min asleep last night.", or None."""
    night = last_night(session, today)
    if night is None:
        return None
    return f"Your band: {health.hours(night.asleep)} asleep last night."
