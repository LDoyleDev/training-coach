"""Band data from Health Connect Webhook (ADR-0055): checking a payload record by record and
storing what it says in our own tables. The payload itself is never kept or logged.

The app sends one JSON object per sync: ``timestamp``, ``app_version`` and an array per data
type with records (docs/webhook.md in mcnaveen/health-connect-webhook). From v1.9.23 a record's
``metadata`` carries its Health Connect ``id``, an edited record comes again with the same id,
and ``deleted`` lists the ids of records removed since the last sync. A night or a workout is
known by that id when there is one, else by where it came from (``metadata.data_origin``) and
when it started; a deleted one is removed. Steps and heart rate are per-day and per-minute
totals, stored by their time, so their ids add nothing and their deletions can't be applied.
A record that doesn't fit is skipped and counted; the rest are stored. The caller owns the
transaction and passes a session bound to the person the secret belongs to.

The app's Test button posts made-up records for yesterday (``MockPayloadBuilder.build``) with a
top-level ``"test": true`` that real syncs never send: those are never parsed or stored.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Self
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import ColumnElement, and_, delete, or_, select
from sqlalchemy.orm import Session

from training_coach.db.models import HealthDay, HeartRateSample, ImportedWorkout, SleepSession
from training_coach.domain import health
from training_coach.domain import zones as domain_zones
from training_coach.domain.health import Minute, SleepMinutes
from training_coach.domain.measurements import Kind
from training_coach.domain.zones import Zones
from training_coach.services import measurements, zones

MAX_AGE = timedelta(days=30)  # the app reads 48 hours back; anything far older is a mistake
AHEAD = timedelta(minutes=10)  # a phone clock a little fast
KEEP_HEART_RATE = timedelta(days=8)
UNKNOWN_SOURCE = "health-connect"
LONGEST = timedelta(hours=24)  # no sleep or workout session is longer
DELETABLE = ("sleep", "exercise")  # kept one row per record, so a deletion can be applied
CHUNK = 500  # ids per query: well inside SQLite's limit on bound parameters


class _Record(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _Meta(_Record):
    data_origin: str = Field(default=UNKNOWN_SOURCE, min_length=1, max_length=128)
    id: str | None = Field(default=None, min_length=1, max_length=128)  # from v1.9.23


class _Span(_Record):
    start_time: AwareDatetime
    end_time: AwareDatetime

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if not self.start_time <= self.end_time <= self.start_time + LONGEST:
            raise ValueError("a span ends after it starts, within a day")
        return self


class _Steps(_Span):
    count: int = Field(ge=0, le=200_000)


class _Stage(_Record):
    stage: int = Field(ge=0, le=99)  # AndroidX STAGE_TYPE_*, sent as a string
    duration_seconds: int = Field(ge=0, le=86_400)


class _Sleep(_Record):
    session_end_time: AwareDatetime
    duration_seconds: int = Field(ge=60, le=86_400)
    stages: list[_Stage] = Field(default_factory=list, max_length=1000)
    metadata: _Meta = Field(default_factory=_Meta)


class _HeartRate(_Record):
    time: AwareDatetime
    bpm: float = Field(ge=25, le=250)  # a sample, or a bucket's average
    min: float | None = Field(default=None, ge=25, le=250)
    max: float | None = Field(default=None, ge=25, le=250)


class _Resting(_Record):
    time: AwareDatetime
    bpm: int = Field(ge=25, le=150)


class _Exercise(_Span):
    type: int = Field(ge=0, le=999)  # AndroidX EXERCISE_TYPE_*, sent as a string
    metadata: _Meta = Field(default_factory=_Meta)


class _Weight(_Record):
    time: AwareDatetime
    kilograms: float = Field(ge=30, le=250)  # as for typed measurements


class _Deleted(_Record):
    type: str = Field(min_length=1, max_length=64)  # the payload key, e.g. "sleep"
    id: str = Field(min_length=1, max_length=128)


@dataclass(frozen=True)
class Sleep:
    source: str
    start: datetime
    end: datetime
    minutes: SleepMinutes
    record_id: str | None = None


@dataclass(frozen=True)
class Exercise:
    source: str
    start: datetime
    end: datetime
    exercise_type: int
    record_id: str | None = None


@dataclass
class Batch:
    """What a payload said, checked. ``taken`` and ``skipped`` count records per type."""

    steps: list[tuple[datetime, int]] = field(default_factory=list)
    sleep: list[Sleep] = field(default_factory=list)
    heart_rate: list[Minute] = field(default_factory=list)
    resting: list[tuple[datetime, int]] = field(default_factory=list)
    exercise: list[Exercise] = field(default_factory=list)
    weight: list[tuple[datetime, float]] = field(default_factory=list)
    deleted: dict[str, set[str]] = field(default_factory=dict)  # ids per type in DELETABLE
    taken: Counter[str] = field(default_factory=Counter)
    skipped: Counter[str] = field(default_factory=Counter)


_MODELS: dict[str, type[_Record]] = {
    "steps": _Steps,
    "sleep": _Sleep,
    "heart_rate": _HeartRate,
    "resting_heart_rate": _Resting,
    "exercise": _Exercise,
    "weight": _Weight,
}


def _when(record: _Record) -> datetime:
    for name in ("start_time", "session_end_time", "time"):
        if (value := getattr(record, name, None)) is not None:
            return value  # type: ignore[no-any-return]  # one of the AwareDatetime fields
    raise AssertionError(record)  # pragma: no cover - every model has one


def is_test(body: dict[str, Any]) -> bool:
    """Whether this is the app's Test button: only a JSON ``true`` counts."""
    return body.get("test") is True


def parse(body: dict[str, Any], now: datetime) -> Batch:
    """Every record of the types we use that validates and is from the last 30 days."""
    batch = Batch()
    readings: list[tuple[datetime, float, float, float]] = []
    for key, model in _MODELS.items():
        records = body.get(key)
        if records is None:
            continue
        if not isinstance(records, list):
            batch.skipped[key] += 1
            continue
        for raw in records:
            try:
                record = model.model_validate(raw)
            except ValidationError:
                batch.skipped[key] += 1
                continue
            if not health.within(_when(record), now, MAX_AGE, AHEAD):
                batch.skipped[key] += 1
                continue
            batch.taken[key] += 1
            _add(batch, record, readings)
    batch.heart_rate = health.per_minute(readings)
    _deletions(batch, body.get("deleted"))
    return batch


def _deletions(batch: Batch, records: object) -> None:
    """The ids of nights and workouts deleted from Health Connect; other types' are ignored."""
    if records is None:
        return
    if not isinstance(records, list):
        batch.skipped["deleted"] += 1
        return
    for raw in records:
        try:
            record = _Deleted.model_validate(raw)
        except ValidationError:
            batch.skipped["deleted"] += 1
            continue
        if record.type in DELETABLE:
            batch.deleted.setdefault(record.type, set()).add(record.id)


def _add(
    batch: Batch, record: _Record, readings: list[tuple[datetime, float, float, float]]
) -> None:
    match record:
        case _Steps():
            batch.steps.append((record.start_time, record.count))
        case _Sleep():
            stages = ((s.stage, s.duration_seconds) for s in record.stages)
            start = record.session_end_time - timedelta(seconds=record.duration_seconds)
            minutes = health.sleep_minutes(record.duration_seconds, stages)
            meta = record.metadata
            batch.sleep.append(
                Sleep(meta.data_origin, start, record.session_end_time, minutes, meta.id)
            )
        case _HeartRate():
            low = record.min if record.min is not None else record.bpm
            high = record.max if record.max is not None else record.bpm
            readings.append((record.time, record.bpm, min(low, record.bpm), max(high, record.bpm)))
        case _Resting():
            batch.resting.append((record.time, record.bpm))
        case _Exercise():
            meta = record.metadata
            batch.exercise.append(
                Exercise(meta.data_origin, record.start_time, record.end_time, record.type, meta.id)
            )
        case _Weight():
            batch.weight.append((record.time, record.kilograms))


# ------------------------------------------------------------------------- storing


def store(session: Session, batch: Batch, tz: ZoneInfo, now: datetime) -> None:
    """Write a checked batch: deletions first, then heart rate, so sleep and workouts can use
    it."""
    nights = _delete(session, batch.deleted)
    _heart_rate(session, batch.heart_rate, now)
    _steps(session, batch.steps, tz)
    _resting_records(session, batch.resting, tz)
    for sleep in batch.sleep:
        _sleep(session, sleep, tz)
    nights |= {s.end.astimezone(tz).date() for s in batch.sleep}
    for minute in batch.heart_rate:
        day = minute.at.astimezone(tz).date()
        nights |= {day, day + timedelta(days=1)}
    today = now.astimezone(tz).date()
    for day in sorted(d for d in nights if d <= today):
        _derive_resting(session, day, tz)
    for exercise in batch.exercise:
        _exercise(session, exercise, tz)
    touched = _refresh_workouts(session, batch)
    session.flush()  # a new peak can raise max heart rate before zones are counted
    if touched:
        hr = zones.current(session, today).zones
        for row in touched:
            count_zones(session, row, hr)
    _weight(session, batch.weight, tz, today)
    session.flush()


def _chunks(ids: set[str]) -> list[list[str]]:
    ordered = sorted(ids)
    return [ordered[n : n + CHUNK] for n in range(0, len(ordered), CHUNK)]


def _delete(session: Session, deleted: dict[str, set[str]]) -> set[date]:
    """Remove the nights and workouts deleted from Health Connect, and return the days whose
    resting heart rate a removed night may have set. A workout already counted stays: it is
    the person's own log now."""
    nights: set[date] = set()
    for ids in _chunks(deleted.get("sleep", set())):
        for row in session.scalars(select(SleepSession).where(SleepSession.record_id.in_(ids))):
            nights.add(row.local_date)
            session.delete(row)
    for ids in _chunks(deleted.get("exercise", set())):
        session.execute(
            delete(ImportedWorkout).where(
                ImportedWorkout.record_id.in_(ids), ImportedWorkout.status != "counted"
            )
        )
    session.flush()
    return nights


def _heart_rate(session: Session, minutes: list[Minute], now: datetime) -> None:
    session.execute(delete(HeartRateSample).where(HeartRateSample.at < now - KEEP_HEART_RATE))
    if not minutes:
        return
    stored = {
        row.at: row
        for row in session.scalars(
            select(HeartRateSample).where(
                HeartRateSample.at >= minutes[0].at, HeartRateSample.at <= minutes[-1].at
            )
        )
    }
    for minute in minutes:
        if minute.at < now - KEEP_HEART_RATE:
            continue
        row = stored.get(minute.at)
        if row is None:
            session.add(
                HeartRateSample(at=minute.at, bpm=minute.bpm, low=minute.low, high=minute.high)
            )
        else:
            row.bpm, row.low, row.high = minute.bpm, minute.low, minute.high
    session.flush()


def _day(session: Session, day: date) -> HealthDay:
    row = session.scalar(select(HealthDay).where(HealthDay.local_date == day))
    if row is None:
        row = HealthDay(local_date=day)
        session.add(row)
    return row


def _steps(session: Session, steps: list[tuple[datetime, int]], tz: ZoneInfo) -> None:
    """A day keeps the larger of what it had and this sync's sum (ADR-0055)."""
    for day, count in health.steps_by_day(steps, tz).items():
        row = _day(session, day)
        row.steps = max(row.steps or 0, min(count, 200_000))


def _resting_records(session: Session, records: list[tuple[datetime, int]], tz: ZoneInfo) -> None:
    lowest: dict[date, int] = {}
    for at, bpm in records:
        day = at.astimezone(tz).date()
        lowest[day] = min(bpm, lowest.get(day, bpm))
    for day, bpm in lowest.items():
        row = _day(session, day)
        if row.resting_source == "record" and row.resting_hr is not None:
            bpm = min(row.resting_hr, bpm)  # a later, partial sync never raises the day's low
        row.resting_hr, row.resting_source = bpm, "record"


def _sleep(session: Session, sleep: Sleep, tz: ZoneInfo) -> None:
    """The payload carries only the end and the length, so a night still being recorded comes
    back with another start. With an id, it is matched by the id, and by overlap with the same
    source only among rows stored without one (before v1.9.23): two records that overlap, a
    nap inside a night, stay two rows (review of #283). Without one, by overlap as before. A
    row with the same source and start is always the same row: they are unique."""
    overlaps = and_(SleepSession.start_at < sleep.end, SleepSession.end_at > sleep.start)
    if sleep.record_id is not None:
        overlaps = and_(overlaps, SleepSession.record_id.is_(None))
    found: ColumnElement[bool] = and_(
        SleepSession.source == sleep.source,
        or_(overlaps, SleepSession.start_at == sleep.start),
    )
    if sleep.record_id is not None:
        found = or_(found, SleepSession.record_id == sleep.record_id)
    same = list(session.scalars(select(SleepSession).where(found).order_by(SleepSession.start_at)))
    if same:
        row, *older = same
        for extra in older:  # one night, sent in pieces before: keep a single row
            session.delete(extra)
        session.flush()
        row.start_at = sleep.start
    else:
        row = SleepSession(source=sleep.source, start_at=sleep.start)
        session.add(row)
    if sleep.record_id is not None:
        row.record_id = sleep.record_id
    m = sleep.minutes
    row.end_at, row.local_date = sleep.end, sleep.end.astimezone(tz).date()
    row.asleep_min, row.awake_min = min(m.asleep, 1440), min(m.awake, 1440)
    row.light_min, row.deep_min, row.rem_min = (
        min(m.light, 1440),
        min(m.deep, 1440),
        min(m.rem, 1440),
    )
    session.flush()


def minutes_between(session: Session, start: datetime, end: datetime) -> list[Minute]:
    rows = session.scalars(
        select(HeartRateSample)
        .where(HeartRateSample.at >= start, HeartRateSample.at <= end)
        .order_by(HeartRateSample.at)
    )
    return [Minute(r.at, r.bpm, r.low, r.high) for r in rows]


def _derive_resting(session: Session, day: date, tz: ZoneInfo) -> None:
    """The night's lowest minute, inside the longest sleep that ended on ``day`` or, without
    one, between midnight and six; a resting heart rate Health Connect had wins."""
    row = session.scalar(select(HealthDay).where(HealthDay.local_date == day))
    if row is not None and row.resting_source == "record":
        return
    sleeps = session.scalars(select(SleepSession).where(SleepSession.local_date == day))
    longest = max(sleeps, key=lambda s: s.end_at - s.start_at, default=None)
    start, end = (longest.start_at, longest.end_at) if longest else health.night(day, tz)
    bpm = health.resting(minutes_between(session, start, end))
    if bpm is None:
        return
    row = row or _day(session, day)
    row.resting_hr, row.resting_source = bpm, "derived"


def _exercise(session: Session, exercise: Exercise, tz: ZoneInfo) -> None:
    row = session.scalar(
        select(ImportedWorkout).where(
            ImportedWorkout.source == exercise.source, ImportedWorkout.start_at == exercise.start
        )
    )
    if exercise.record_id is not None:
        same = session.scalar(
            select(ImportedWorkout)
            .where(ImportedWorkout.record_id == exercise.record_id)
            .order_by(ImportedWorkout.id)
        )
        if same is not None and same is not row:
            # Its start was edited since it came: one workout, so one row, keeping the one the
            # person counted or dismissed. Two acted on are left as they are.
            if row is None:
                row = same
            elif row.status == "new":
                session.delete(row)
                session.flush()
                row = same
            elif same.status == "new":
                session.delete(same)
                session.flush()
    if row is None:
        row = ImportedWorkout(source=exercise.source, start_at=exercise.start, status="new")
        session.add(row)
    row.start_at = exercise.start
    if exercise.record_id is not None:
        row.record_id = exercise.record_id
    activity = health.activity_for(exercise.exercise_type)
    row.end_at, row.exercise_type = exercise.end, exercise.exercise_type
    row.local_date = exercise.start.astimezone(tz).date()
    row.activity = activity.value if activity is not None else None
    row.minutes = int((exercise.end - exercise.start).total_seconds() // 60)
    session.flush()


def _refresh_workouts(session: Session, batch: Batch) -> list[ImportedWorkout]:
    """Heart-rate figures for workouts in this batch, and for any whose window this batch's
    heart rate reaches (it can arrive a sync later than the workout)."""
    spans = [(e.start, e.end) for e in batch.exercise]
    if batch.heart_rate:
        spans.append((batch.heart_rate[0].at, batch.heart_rate[-1].at))
    seen: dict[int, ImportedWorkout] = {}
    for start, end in spans:
        for row in session.scalars(
            select(ImportedWorkout).where(
                ImportedWorkout.start_at <= end, ImportedWorkout.end_at >= start
            )
        ):
            if row.id not in seen:
                seen[row.id] = row
                refresh(session, row)
    return list(seen.values())


def refresh(session: Session, row: ImportedWorkout) -> None:
    """A workout's average and highest heart rate from the minutes in its window."""
    minutes = minutes_between(session, row.start_at, row.end_at)
    if not minutes:
        return
    row.avg_hr = round(sum(m.bpm for m in minutes) / len(minutes))
    row.max_hr = max(m.high for m in minutes)


def count_zones(session: Session, row: ImportedWorkout, hr: Zones) -> None:
    """Minutes in each zone from the heart rate kept for the workout's window; left as they
    were once that heart rate is gone (after 8 days)."""
    minutes = minutes_between(session, row.start_at, row.end_at)
    if not minutes:
        return
    found = domain_zones.minutes([(m.at, m.bpm) for m in minutes], row.end_at, hr)
    row.zone1_min, row.zone2_min, row.zone3_min, row.zone4_min, row.zone5_min = found


def rezone(session: Session, today: date, now: datetime) -> None:
    """Count zone minutes again with the zones as they are now, for every workout whose heart
    rate is still kept: after the birth year or max heart rate changed."""
    hr = zones.current(session, today).zones
    recent = select(ImportedWorkout).where(ImportedWorkout.end_at >= now - KEEP_HEART_RATE)
    for row in session.scalars(recent):
        count_zones(session, row, hr)
    session.flush()


def _weight(
    session: Session, readings: list[tuple[datetime, float]], tz: ZoneInfo, today: date
) -> None:
    """The first reading of each day, into Body, never over a value already there."""
    first: dict[date, tuple[datetime, float]] = {}
    for at, kilograms in sorted(readings):
        first.setdefault(at.astimezone(tz).date(), (at, kilograms))
    for day, (_, kilograms) in first.items():
        measurements.fill(session, day, today, Kind.BODYWEIGHT, round(kilograms, 1))


def counts(batch: Batch) -> dict[str, int]:
    """How many records of each type were taken and skipped: all that is ever logged."""
    found: dict[str, int] = defaultdict(int)
    for key, n in batch.taken.items():
        found[key] = n
    for key, n in batch.skipped.items():
        found[f"{key}_skipped"] = n
    for key, ids in batch.deleted.items():
        found[f"{key}_deleted"] = len(ids)
    return dict(found)
