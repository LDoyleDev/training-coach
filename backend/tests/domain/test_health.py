from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from training_coach.domain import health
from training_coach.domain.enums import CardioActivity
from training_coach.domain.health import Minute, SleepMinutes

BERLIN = ZoneInfo("Europe/Berlin")
T = datetime(2026, 10, 11, 2, 0, tzinfo=UTC)


def test_cardio_exercise_types_have_an_activity_and_others_none() -> None:
    assert health.activity_for(79) is CardioActivity.WALK
    assert health.activity_for(57) is CardioActivity.RUN  # treadmill
    assert health.activity_for(9) is CardioActivity.BIKE
    assert health.activity_for(70) is None  # strength training
    assert health.activity_for(0) is None  # "other workout": not offered


def test_sleep_minutes_per_stage() -> None:
    stages = [(4, 3600), (2, 600), (5, 1800), (6, 1500), (1, 300), (7, 120), (3, 60), (0, 900)]
    assert health.sleep_minutes(9000, stages) == SleepMinutes(
        asleep=60 + 10 + 30 + 25, awake=5 + 2 + 1, light=70, deep=30, rem=25
    )


def test_sleep_without_stages_was_all_asleep() -> None:
    assert health.sleep_minutes(27_000, []) == SleepMinutes(450, 0, 0, 0, 0)


def test_readings_become_one_row_per_minute() -> None:
    readings = [
        (T + timedelta(seconds=5), 60.0, 60.0, 60.0),
        (T + timedelta(seconds=35), 64.0, 64.0, 64.0),
        (T + timedelta(minutes=1), 70.0, 66.0, 81.0),
        (T.astimezone(BERLIN) - timedelta(minutes=1), 50.4, 49.0, 52.0),  # any zone, in order
    ]
    assert health.per_minute(readings) == [
        Minute(T - timedelta(minutes=1), 50, 49, 52),
        Minute(T, 62, 60, 64),
        Minute(T + timedelta(minutes=1), 70, 66, 81),
    ]


def test_steps_are_summed_per_local_day_of_their_start() -> None:
    late = datetime(2026, 10, 10, 21, 59, tzinfo=UTC)  # 23:59 in Berlin
    after_midnight = datetime(2026, 10, 10, 22, 1, tzinfo=UTC)
    assert health.steps_by_day([(late, 100), (late, 50), (after_midnight, 7)], BERLIN) == {
        date(2026, 10, 10): 150,
        date(2026, 10, 11): 7,
    }


def test_the_night_is_midnight_to_six_local_time_in_utc() -> None:
    assert health.night(date(2026, 10, 11), BERLIN) == (
        datetime(2026, 10, 10, 22, 0, tzinfo=UTC),
        datetime(2026, 10, 11, 4, 0, tzinfo=UTC),
    )
    winter = health.night(date(2026, 12, 1), BERLIN)
    assert winter[0] == datetime(2026, 11, 30, 23, 0, tzinfo=UTC)


def test_resting_is_the_lowest_minute_of_enough_minutes() -> None:
    minutes = [Minute(T + timedelta(minutes=n), 55 - (n == 7) * 6, 40, 60) for n in range(20)]
    assert health.resting(minutes) == 49
    assert health.resting(minutes[:19]) is None


def test_believable_times() -> None:
    back, ahead = timedelta(days=30), timedelta(minutes=10)
    assert health.within(T - timedelta(days=29), T, back, ahead)
    assert not health.within(T - timedelta(days=31), T, back, ahead)
    assert health.within(T + timedelta(minutes=9), T, back, ahead)
    assert not health.within(T + timedelta(minutes=11), T, back, ahead)
