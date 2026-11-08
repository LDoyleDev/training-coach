"""The starters' gym versions (any-level-any-time.md S1, Decided 5)."""

import pytest

from training_coach.domain.gym_swaps import Swap, swap_for

ROW = Swap("doorway-row", 1, "chest-supported-row", 8, 12)
PULLDOWN = Swap("doorway-row", 1, "lat-pulldown", 8, 12, frozenset({"three-days-b"}))
SQUAT = Swap("goblet-squat", 5, "leg-press", 10, 15)
SWAPS = (ROW, PULLDOWN, SQUAT)


@pytest.mark.parametrize(
    ("session", "exercise", "placed", "expected"),
    [
        ("three-days-a", "goblet-squat", 4, None),  # below its step: the home squat stays
        ("three-days-a", "goblet-squat", 5, SQUAT),  # from its step
        ("three-days-a", "goblet-squat", 9, SQUAT),  # and above
        ("three-days-a", "doorway-row", 1, ROW),
        ("three-days-b", "doorway-row", 1, PULLDOWN),  # the session's own swap first
        ("three-days-b", "doorway-row", 0, None),
        ("three-days-a", "plank", 4, None),  # stays at the gym
    ],
)
def test_an_item_swaps_from_its_step_and_a_sessions_own_swap_comes_first(
    session: str, exercise: str, placed: int, expected: Swap | None
) -> None:
    assert swap_for(SWAPS, session, exercise, placed) == expected


def test_a_swap_for_some_sessions_only_is_in_no_other() -> None:
    assert swap_for((PULLDOWN,), "three-days-a", "doorway-row", 4) is None
