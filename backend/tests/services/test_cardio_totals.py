"""All cardio in the last 7 days, split by heart-rate zone (ADR-0079), from Liam's week of
20-26 Oct 2026: zones from resting 49 and max 174 (born 1977), zone 2 124-136 bpm."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    HealthDay,
    HeartRateSample,
    ImportedWorkout,
    SessionTemplate,
    SetLog,
    Workout,
)
from training_coach.domain.cardio import Details, Targets
from training_coach.domain.enums import CardioActivity
from training_coach.services import (
    ai_summary,
    band_cardio,
    cardio,
    cardio_totals,
    day_clash,
    day_view,
    home,
    progress,
    review,
    user_settings,
    zones,
)
from training_coach.services.seed import apply_seed, load_plan

TZ = ZoneInfo("Europe/Berlin")
MONDAY = date(2026, 10, 26)
THURSDAY = date(2026, 10, 23)
WALK_AT = datetime.combine(MONDAY, time(7, 0), tzinfo=TZ).astimezone(UTC)
# Monday's walk minute by minute: 20 easy, 7 in zone 1, 35 in zone 2, 4 in zone 3.
WALK = [105] * 20 + [118] * 7 + [130] * 35 + [140] * 4


@pytest.fixture
def week(session: Session) -> Session:
    apply_seed(session, load_plan())
    zones.save(session, 1977, None)
    session.add(HealthDay(local_date=MONDAY, resting_hr=49))
    session.flush()
    return session


def _log(
    session: Session, kind: str, minutes: int, on: date, started_at: datetime | None = None
) -> int:
    activity = CardioActivity.RUN if kind == cardio.MODERATE else CardioActivity.WALK
    details = Details(started_at=started_at)
    token = uuid4().hex
    logged = cardio.log(
        session, on, TZ, kind, minutes, activity, token, extra=True, details=details
    )
    assert isinstance(logged, cardio.Logged)
    session.flush()
    return logged.saved.workout_id


def _samples(session: Session, start: datetime, rates: list[int]) -> None:
    for n, bpm in enumerate(rates):
        session.add(HeartRateSample(at=start + timedelta(minutes=n), bpm=bpm, low=bpm, high=bpm))
    session.flush()


def _band_walk(session: Session, workout_id: int | None = None) -> ImportedWorkout:
    row = ImportedWorkout(
        source="com.mi.health",
        start_at=WALK_AT,
        end_at=WALK_AT + timedelta(minutes=66),
        local_date=MONDAY,
        exercise_type=79,
        activity="walk",
        minutes=66,
        avg_hr=124,
        status="counted" if workout_id else "new",
        workout_id=workout_id,
    )
    row.zone1_min, row.zone2_min, row.zone3_min, row.zone4_min, row.zone5_min = (7, 35, 4, 0, 0)
    session.add(row)
    session.flush()
    return row


def _liams_week(session: Session) -> None:
    """Thursday's typed run, and Monday's walk as Count it logged it then: its zone 2 minutes."""
    _log(session, cardio.MODERATE, 43, THURSDAY)
    _band_walk(session, _log(session, cardio.ZONE2, 35, MONDAY))
    _samples(session, WALK_AT, WALK)


def test_liams_week_counts_all_of_mondays_walk(week: Session) -> None:
    _liams_week(week)
    found = cardio.week(week, MONDAY)
    assert (found.total, found.zone2, found.moderate) == (109, 35, 43)
    assert found.zones.measured == (20, 7, 35, 4, 0, 0)  # the walk, from its heart rate
    assert found.zones.harder_unmeasured == 43  # the run: zone 3+, no heart rate
    # Against the cycle: Long zone 2 45-75 min, plus Cardio + core's 30-40 min for the total.
    assert (found.zone2_target, found.total_target) == ((45, 75), (75, 115))


def test_home_and_the_review_agree(week: Session) -> None:
    _liams_week(week)
    found = home.home(week, MONDAY, TZ)
    assert (found.week.cardio.total, found.week.zone2_minutes) == (109, 35)
    assert found.totals.cardio_minutes == 109  # all time too
    assert [r.session for r in found.recent] == ["Walk, 66 min", "Run, 43 min"]
    weekly = review.weekly(week, MONDAY, TZ)  # Monday to Sunday: only the walk
    assert (weekly.zone2_minutes, weekly.moderate_minutes) == (35, 0)


def test_once_its_heart_rate_is_gone_the_bands_zones_count(week: Session) -> None:
    _band_walk(week, _log(week, cardio.ZONE2, 35, MONDAY))  # no samples kept
    found = cardio.week(week, MONDAY)
    assert (found.total, found.zone2, found.zones.measured) == (66, 35, (20, 7, 35, 4, 0, 0))


def test_a_typed_log_with_a_start_splits_by_the_band_worn_then(week: Session) -> None:
    start = WALK_AT + timedelta(hours=3)
    _samples(week, start, [130] * 20 + [150] * 10)  # 20 in zone 2, 10 in zone 4
    _log(week, cardio.ZONE2, 40, MONDAY, started_at=start)
    found = cardio.week(week, MONDAY)
    assert found.zones.measured == (0, 0, 20, 0, 14, 0)  # the last reading runs 5 minutes
    assert (found.total, found.zone2, found.zones.zone2_unmeasured) == (40, 26, 6)


def test_hiit_logs_rounds_and_stays_out(week: Session) -> None:
    logged = cardio.log(week, MONDAY, TZ, cardio.HIIT, 8, None, uuid4().hex, extra=True)
    assert isinstance(logged, cardio.Logged)
    assert cardio.week(week, MONDAY).total == 0


def test_count_it_now_logs_the_whole_walk(week: Session) -> None:
    walk = _band_walk(week)
    _samples(week, WALK_AT, WALK)
    counted = band_cardio.count(week, walk.id, MONDAY, TZ)
    assert isinstance(counted, band_cardio.Counted)
    values = week.scalars(select(SetLog.value).where(SetLog.workout_id == counted.workout_id))
    assert list(values) == [66]
    found = cardio.week(week, MONDAY)
    assert (found.total, found.zone2, found.moderate) == (66, 35, 0)


def test_the_targets_are_the_cycles_cardio_plus_extra(week: Session) -> None:
    assert cardio_totals.targets(week) == Targets((45, 75), (75, 115))
    user_settings.update(week, extra_cardio_min=60)  # walks outside the sessions: easy cardio
    assert cardio_totals.targets(week) == Targets((105, 135), (135, 175))


def test_the_day_view_shows_mondays_walk_as_66_minutes(week: Session) -> None:
    """Counted before ADR-0079, it holds 35; the day view says what the totals count."""
    _liams_week(week)
    (walk,) = day_view.logged(week, MONDAY)
    (zone2,) = walk.exercises
    assert (zone2.unit, [s.left for s in zone2.sets]) == ("minutes", [66])
    (run,) = day_view.logged(week, THURSDAY)  # a typed log: as logged
    assert [s.left for s in run.exercises[0].sets] == [43]


def test_every_reader_of_the_walks_minutes_says_66(week: Session) -> None:
    """Bests and Telegram's /progress (``progress``), what a connected AI reads (the summary
    and an exercise's history over MCP) and the day-clash question: none shows the stored 35."""
    _liams_week(week)
    (zone2,) = [s for s in progress.overview(week) if s.slug == "zone2"]
    assert zone2.best_set == 66
    read = ai_summary.summary(week, MONDAY, ai_summary.Options(weeks=None))
    history = ai_summary.exercise(week, "zone2", None)
    assert history is not None
    assert "66" in read
    assert "66" in history
    assert "35" not in history
    walk = week.scalars(select(Workout).where(Workout.local_date == MONDAY)).one()
    walk.template_id = week.scalars(
        select(SessionTemplate.id).where(SessionTemplate.slug == "zone2")
    ).one()  # it completed Long zone 2, as Count it does on its day
    week.flush()
    clash = day_clash.recorded(week, MONDAY)
    assert clash is not None
    assert clash.recorded[0].summary == "66 min"
