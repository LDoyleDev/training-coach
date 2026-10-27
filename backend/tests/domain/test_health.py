from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

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


@pytest.mark.parametrize(
    ("activity", "minutes", "zones", "expected"),
    [
        (CardioActivity.WALK, 46, [8, 38, 0, 0, 0], ("zone2", 46)),  # all of it (ADR-0079)
        (CardioActivity.RUN, 32, [0, 6, 20, 6, 0], ("moderate-cardio", 32)),  # zones 3-5 win
        (CardioActivity.BIKE, 40, [0, 10, 10, 0, 0], ("zone2", 40)),  # a tie is zone 2
        (CardioActivity.WALK, 30, None, ("zone2", 30)),  # no heart rate
        (CardioActivity.RUN, 25, None, ("moderate-cardio", 25)),
        (CardioActivity.STAIRS, 12, None, ("moderate-cardio", 12)),
        (CardioActivity.WALK, 40, [36, 4, 0, 0, 0], None),  # under 5 minutes of zone 2
    ],
)
def test_what_a_band_workout_counts_as(
    activity: CardioActivity,
    minutes: int,
    zones: list[int] | None,
    expected: tuple[str, int] | None,
) -> None:
    assert health.counted_as(activity, minutes, zones) == expected


def test_the_question() -> None:
    walk = CardioActivity.WALK
    assert health.offer_text(walk, 46, [8, 38, 0, 0, 0]) == "Walk, 46 min, 38 in zone 2 - count it?"
    assert health.offer_text(CardioActivity.RUN, 32, [0, 6, 20, 6, 0]) == (
        "Run, 32 min, 26 in zones 3-5 - count it?"
    )
    assert health.offer_text(CardioActivity.OTHER, 20, None) == "Cardio, 20 min - count it?"


@pytest.mark.parametrize(
    ("asleep", "answer"), [(480, "good"), (420, "good"), (419, "ok"), (360, "ok"), (359, "poor")]
)
def test_the_sleep_answer_a_night_suggests(asleep: int, answer: str) -> None:
    assert health.sleep_answer(asleep) == answer


def test_hours() -> None:
    assert [health.hours(m) for m in (440, 420, 45, 0)] == ["7 h 20 min", "7 h", "45 min", "0 min"]
