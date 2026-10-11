"""A person's heart-rate zones (ADR-0054): their settings, recent nights and workouts, put
through ``domain.zones``. The caller passes a session bound to the person."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import HealthDay, ImportedWorkout, UserSettings
from training_coach.domain import zones
from training_coach.domain.zones import Zones
from training_coach.services import users

LOWEST_MAX, HIGHEST_MAX = 120, 230  # a max heart rate typed in must be in this range
FIRST_YEAR, LAST_YEAR = 1920, 2020  # and a birth year in this one


@dataclass(frozen=True)
class HeartRate:
    """What the zones come from, for showing them."""

    birth_year: int | None
    own_max: int | None  # typed in; wins over everything
    estimated_max: int | None  # 208 - 0.7 x age
    peak: int | None  # the highest any imported workout reached
    zones: Zones


def current(session: Session, today: date) -> HeartRate:
    found = users.settings_row(session)
    birth_year = found.birth_year if found is not None else None
    own = found.max_hr if found is not None else None
    years = zones.age(birth_year, today.year)
    peak = session.scalar(select(func.max(ImportedWorkout.max_hr)))
    nights = list(
        session.scalars(
            select(HealthDay.resting_hr)
            .where(HealthDay.resting_hr.is_not(None), HealthDay.local_date <= today)
            .order_by(HealthDay.local_date.desc())
            .limit(zones.NIGHTS)
        )
    )
    top = zones.max_heart_rate(own, years, peak)
    return HeartRate(
        birth_year,
        own,
        zones.estimated_max(years) if years is not None else None,
        peak,
        zones.karvonen(zones.resting([n for n in nights if n is not None]), top),
    )


def problem(birth_year: int | None, own_max: int | None) -> str | None:
    """Why these settings can't be saved, or None."""
    if birth_year is not None and not FIRST_YEAR <= birth_year <= LAST_YEAR:
        return f"birth year must be from {FIRST_YEAR} to {LAST_YEAR}"
    if own_max is not None and not LOWEST_MAX <= own_max <= HIGHEST_MAX:
        return f"max heart rate must be from {LOWEST_MAX} to {HIGHEST_MAX}"
    return None


def save(session: Session, birth_year: int | None, own_max: int | None) -> None:
    """Store the birth year and own max heart rate (either may be empty). The caller checks
    ``problem`` first."""
    found = users.settings_row(session)
    if found is None:
        found = UserSettings()
        session.add(found)
    found.birth_year, found.max_hr = birth_year, own_max
    session.flush()
