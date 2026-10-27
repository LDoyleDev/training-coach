import pytest

from training_coach.domain.cardio import (
    NO_DETAILS,
    Details,
    Targets,
    activity_in,
    by_speed,
    details_problem,
    left,
    load,
    pace,
    speed,
    suggested,
    targets,
)
from training_coach.domain.enums import CardioActivity
from training_coach.domain.zones import karvonen


@pytest.mark.parametrize(
    ("text", "activity"),
    [
        ("walk 45", CardioActivity.WALK),
        ("Walked 45 min", CardioActivity.WALK),
        ("hiked for 90 minutes", CardioActivity.HIKE),
        ("easy run 30", CardioActivity.RUN),
        ("cycled 60", CardioActivity.BIKE),
        ("zone 2 40 min on the bike", CardioActivity.BIKE),
        ("jogging 25", CardioActivity.JOG),
        ("swam 30", CardioActivity.SWIM),
        ("rowing 20", CardioActivity.ROW),
        ("stairs 15", CardioActivity.STAIRS),
    ],
)
def test_an_activity_is_read_from_the_words(text: str, activity: CardioActivity) -> None:
    assert activity_in(text) == activity


@pytest.mark.parametrize("text", ["zone 2 45", "cardio 30", "walked then cycled, 60", ""])
def test_none_or_several_leave_it_empty(text: str) -> None:
    assert activity_in(text) is None


def test_details_within_bounds_have_no_problem() -> None:
    found = Details(effort=6, distance_m=7290, avg_hr=139, max_hr=160)
    assert details_problem(found, rounds=False) is None
    assert details_problem(NO_DETAILS, rounds=True) is None
    assert found
    assert not NO_DETAILS


@pytest.mark.parametrize(
    ("details", "rounds", "problem"),
    [
        (Details(effort=0), False, "effort must be between 1 and 10"),
        (Details(effort=11), False, "effort must be between 1 and 10"),
        (Details(distance_m=0), False, "distance must be between 0 and 300 km"),
        (Details(distance_m=300_001), False, "distance must be between 0 and 300 km"),
        (Details(distance_m=5000), True, "HIIT is counted in rounds: no distance"),
        (Details(avg_hr=29), False, "average heart rate must be between 30 and 230"),
        (Details(max_hr=231), False, "highest heart rate must be between 30 and 230"),
        (Details(avg_hr=150, max_hr=140), False, "highest heart rate can't be below the average"),
    ],
)
def test_details_out_of_bounds_say_why(details: Details, rounds: bool, problem: str) -> None:
    assert details_problem(details, rounds=rounds) == problem


def test_pace_is_seconds_per_km_and_needs_a_distance() -> None:
    assert pace(43, 7290) == 354  # 5:54 a km
    assert pace(43, None) is None
    assert pace(0, 7290) is None


def test_speed_is_km_per_hour_and_needs_a_distance() -> None:
    assert speed(90, 36000) == 24.0
    assert speed(90, None) is None
    assert speed(0, 36000) is None


def test_only_a_ride_is_read_by_its_speed() -> None:
    assert by_speed(CardioActivity.BIKE)
    assert not by_speed(CardioActivity.RUN)
    assert not by_speed(None)


@pytest.mark.parametrize(
    ("avg_hr", "kind"),
    [
        (100, "zone2"),
        (138, "zone2"),
        (150, "zone2"),
        (151, "moderate-cardio"),
        (200, "moderate-cardio"),
    ],
)
def test_an_average_heart_rate_suggests_a_kind(avg_hr: int, kind: str) -> None:
    zones = karvonen(60, 190)  # zone 2 is 138 bpm up to 151: 60 + 130 x 0.6 to 0.7
    assert zones.bounds[1] == (138, 151)
    assert suggested(avg_hr, zones) == kind


def test_load_is_minutes_times_effort() -> None:
    assert load(43, 6) == 258
    assert load(43, None) is None


@pytest.mark.parametrize(
    ("done", "target", "expected"),
    [
        (0, 180, 180),  # nothing yet: all of it
        (179, 180, 1),
        (180, 180, 0),  # the low end of zone 2's 180-200: on target
        (200, 180, 0),
        (239, 240, 1),
        (240, 240, 0),  # the total's 240
        (300, 240, 0),  # over: never negative
        (35, None, None),  # no target in the plan
    ],
)
def test_what_is_left_of_a_cardio_target(done: int, target: int | None, expected: int) -> None:
    assert left(done, target) == expected


def test_targets_are_the_cycles_cardio_plus_extra() -> None:
    assert targets((45, 75), (30, 40), 0) == Targets((45, 75), (75, 115))
    assert targets((45, 75), (30, 40), 30) == Targets((75, 105), (105, 145))
    assert targets(None, (30, 40), 0) == Targets(None, (30, 40))  # no zone 2 session
    assert targets(None, None, 60) == Targets((60, 60), (60, 60))  # extra cardio only
    assert targets(None, None, 0) == Targets(None, None)  # nothing to aim for
