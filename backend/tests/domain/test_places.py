"""Where today's session is done (ADR-0071, Decided 4; ADR-0086)."""

import pytest

from training_coach.domain.enums import Place, Places
from training_coach.domain.places import choices, day_place, no_kit_step

HOME, GYM, AWAY = Place.HOME, Place.GYM, Place.AWAY


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


@pytest.mark.parametrize(
    ("places", "gym", "away", "expected"),
    [
        (Places.BOTH, True, True, (HOME, GYM, AWAY)),
        (Places.BOTH, True, False, (HOME, GYM)),
        (Places.BOTH, False, True, (HOME, AWAY)),  # done the same way at the gym
        (Places.HOME, True, True, (HOME, AWAY)),  # away also for someone at home only
        (Places.GYM, True, True, (GYM, AWAY)),
        (Places.GYM, False, True, (HOME, AWAY)),  # no gym version: done as at home
        (Places.HOME, False, False, (HOME,)),
        (Places.GYM, True, False, (GYM,)),
    ],
)
def test_the_switch_offers_the_days_places_and_away_with_an_away_version(
    places: Places, gym: bool, away: bool, expected: tuple[Place, ...]
) -> None:
    assert choices(places, has_gym_version=gym, has_away_version=away) == expected


@pytest.mark.parametrize(
    ("free", "at", "expected"),
    [
        ((True, True, False), 1, 1),  # the level needs no kit: trained there
        ((True, True, False), 2, 1),  # it does: the highest step below that needs none
        ((True, False, True, False, False), 4, 2),
        ((True, False, False), 2, 0),
        ((False, False), 1, 1),  # nothing below needs no kit: the level as it is
        ((False, True), 0, 0),  # never above the level
    ],
)
def test_away_trains_the_highest_step_at_or_below_the_level_that_needs_no_kit(
    free: tuple[bool, ...], at: int, expected: int
) -> None:
    assert no_kit_step(free, at) == expected
