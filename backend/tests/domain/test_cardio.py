import pytest

from training_coach.domain.cardio import (
    NO_DETAILS,
    Details,
    activity_in,
    details_problem,
    load,
    pace,
)
from training_coach.domain.enums import CardioActivity


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


def test_load_is_minutes_times_effort() -> None:
    assert load(43, 6) == 258
    assert load(43, None) is None
