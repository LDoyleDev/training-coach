"""Where today's session is done (ADR-0071, Decided 4)."""

import pytest

from training_coach.domain.enums import Place, Places
from training_coach.domain.places import can_switch, day_place


@pytest.mark.parametrize(
    ("places", "last", "expected"),
    [
        (Places.HOME, Place.GYM, Place.HOME),
        (Places.GYM, Place.HOME, Place.GYM),
        (Places.BOTH, Place.GYM, Place.GYM),
        (Places.BOTH, Place.HOME, Place.HOME),
    ],
)
def test_one_place_is_that_place_and_both_is_the_last_chosen(
    places: Places, last: Place, expected: Place
) -> None:
    assert day_place(places, last) is expected


def test_the_switch_needs_both_places_and_a_gym_version() -> None:
    assert can_switch(Places.BOTH, has_gym_version=True)
    assert not can_switch(Places.BOTH, has_gym_version=False)
    assert not can_switch(Places.HOME, has_gym_version=True)
    assert not can_switch(Places.GYM, has_gym_version=True)
