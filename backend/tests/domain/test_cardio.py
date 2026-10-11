import pytest

from training_coach.domain.cardio import activity_in
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
