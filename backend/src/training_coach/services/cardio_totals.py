"""Cardio minutes from done workouts, and how they split by heart-rate zone (ADR-0079).

A cardio log is sets of the zone2 or moderate-cardio exercise, valued in minutes: the
stored value is the truth, so a person's edit always counts (a walk counted before ADR-0079
held only its zone 2 minutes; a data migration gave it its full minutes). Minutes split by the
zone of each minute's heart rate kept for the workout's window (8 days, ADR-0055): a workout
counted from the band (``imported_workouts.workout_id``) has the band's window, and once that
heart rate is gone, the band's own zone minutes; a typed log with a start (ADR-0067) splits the
same way when the band was worn then. Heart rate over more minutes than were logged is trimmed
from the largest zones. Minutes without heart rate count in the zone the person logged them as.
HIIT logs rounds and has no window, so it stays out. It only reads; the caller passes a session
bound to the person.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Exercise,
    HeartRateSample,
    ImportedWorkout,
    SetLog,
    TemplateItem,
    Workout,
)
from training_coach.domain import cardio
from training_coach.domain import zones as domain_zones
from training_coach.domain.cardio import Targets
from training_coach.domain.enums import WorkoutStatus
from training_coach.domain.health import MODERATE, ZONE2
from training_coach.domain.zones import Split, Zones
from training_coach.services import user_settings, zones

KINDS = (ZONE2, MODERATE)


def targets(session: Session) -> Targets:
    """The cardio targets for 7 days (ADR-0079): from the cycle's sessions, so a plan change
    moves them, plus the person's extra cardio a week. The one place they come from."""
    rows = session.execute(
        select(
            Exercise.slug,
            func.sum(TemplateItem.sets * TemplateItem.rep_min),
            func.sum(TemplateItem.sets * TemplateItem.rep_max),
        )
        .join(TemplateItem, TemplateItem.exercise_id == Exercise.id)
        .where(Exercise.slug.in_(KINDS))
        .group_by(Exercise.slug)
    )
    planned = {slug: (int(low), int(high)) for slug, low, high in rows}
    extra = user_settings.load(session).extra_cardio_min
    return cardio.targets(planned.get(ZONE2), planned.get(MODERATE), extra)


@dataclass(frozen=True)
class Logged:
    """One done workout's cardio."""

    workout_id: int
    minutes: dict[str, int]  # by exercise slug
    window: tuple[datetime, datetime] | None  # when it was done, if known
    band: tuple[int, ...] | None  # the band's minutes in zones 1-5, for a counted import

    @property
    def total(self) -> int:
        return sum(self.minutes.values())


def logged(session: Session, start: date, end: date) -> list[Logged]:
    """The cardio of each done workout from local day ``start`` to ``end``, both included."""
    rows = session.execute(
        select(Workout.id, Workout.started_at, Exercise.slug, func.sum(SetLog.value))
        .join(SetLog, SetLog.workout_id == Workout.id)
        .join(Exercise, Exercise.id == SetLog.exercise_id)
        .where(
            Workout.local_date >= start,
            Workout.local_date <= end,
            Workout.status == WorkoutStatus.DONE,
            Exercise.slug.in_(KINDS),
        )
        .group_by(Workout.id, Workout.started_at, Exercise.slug)
    )
    found: dict[int, tuple[datetime | None, dict[str, int]]] = {}
    for workout_id, started, slug, total in rows:
        found.setdefault(workout_id, (started, {}))[1][slug] = int(total)
    band = {
        row.workout_id: row
        for row in session.scalars(
            select(ImportedWorkout).where(ImportedWorkout.workout_id.in_(found))
        )
    }
    return [_logged(n, started, minutes, band.get(n)) for n, (started, minutes) in found.items()]


def _logged(
    workout_id: int, started: datetime | None, minutes: dict[str, int], row: ImportedWorkout | None
) -> Logged:
    if row is not None:
        stored = (row.zone1_min, row.zone2_min, row.zone3_min, row.zone4_min, row.zone5_min)
        band = tuple(m for m in stored if m is not None)
        window = (row.start_at, row.end_at)
        return Logged(workout_id, minutes, window, band if len(band) == 5 else None)
    total = sum(minutes.values())
    typed = (started, started + timedelta(minutes=total)) if started is not None else None
    return Logged(workout_id, minutes, typed, None)


def by_kind(found: Iterable[Logged]) -> dict[str, int]:
    """Minutes per cardio exercise (slug)."""
    totals: dict[str, int] = defaultdict(int)
    for one in found:
        for slug, minutes in one.minutes.items():
            totals[slug] += minutes
    return dict(totals)


def split(session: Session, found: Iterable[Logged], on: date) -> Split:
    """All of ``found``'s minutes by zone, with the person's zones as they are on ``on``."""
    hr = zones.current(session, on).zones
    total = Split()
    for one in found:
        total += _split(session, one, hr)
    return total


def _split(session: Session, one: Logged, hr: Zones) -> Split:
    harder = one.minutes.get(MODERATE, 0) > one.minutes.get(ZONE2, 0)
    if one.window is not None and (readings := _heart_rate(session, *one.window)):
        return domain_zones.split(
            one.total, harder, domain_zones.measured(readings, one.window[1], hr)
        )
    if one.band is not None:  # its heart rate is gone: the band's zones, the rest below zone 1
        below = max(0, one.total - sum(one.band))
        return domain_zones.split(one.total, harder, (below, *one.band))
    return sum(
        (domain_zones.split(m, slug == MODERATE) for slug, m in one.minutes.items()), Split()
    )


def _heart_rate(session: Session, start: datetime, end: datetime) -> list[tuple[datetime, int]]:
    rows = session.execute(
        select(HeartRateSample.at, HeartRateSample.bpm)
        .where(HeartRateSample.at >= start, HeartRateSample.at <= end)
        .order_by(HeartRateSample.at)
    )
    return [(at, bpm) for at, bpm in rows]
