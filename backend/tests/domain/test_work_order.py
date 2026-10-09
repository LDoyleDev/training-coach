import pytest

from training_coach.domain.work_order import work_order


def test_a_pair_alternates_set_by_set() -> None:
    assert work_order([3, 3], [1, 1]) == [[(0, 1), (1, 1), (0, 2), (1, 2), (0, 3), (1, 3)]]


def test_the_longer_exercise_finishes_its_sets_alone() -> None:
    assert work_order([2, 4], [1, 1]) == [[(0, 1), (1, 1), (0, 2), (1, 2), (1, 3), (1, 4)]]
    assert work_order([3, 1], [2, 2]) == [[(0, 1), (1, 1), (0, 2), (0, 3)]]


def test_unpaired_items_are_done_straight_through_in_their_own_group() -> None:
    assert work_order([2, 2, 1], [1, 1, None]) == [
        [(0, 1), (1, 1), (0, 2), (1, 2)],
        [(2, 1)],
    ]
    assert work_order([2, 1], [None, None]) == [[(0, 1), (0, 2)], [(1, 1)]]


@pytest.mark.parametrize(
    "pairs",
    [
        [1, None, 1],  # not neighbours
        [1, 1, 1],  # three items share a number
        [1, None, None],  # alone
    ],
)
def test_a_broken_pair_falls_back_to_doing_items_in_order(pairs: list[int | None]) -> None:
    flat = [ref for group in work_order([1, 1, 1], pairs) for ref in group]
    assert sorted(flat) == [(0, 1), (1, 1), (2, 1)]  # nothing lost or repeated


def test_no_sets_no_group_and_mismatched_lengths_raise() -> None:
    assert work_order([0, 2], [None, None]) == [[(1, 1), (1, 2)]]
    assert work_order([], []) == []
    with pytest.raises(ValueError, match="same items"):
        work_order([1], [])


def test_a_pair_can_start_with_its_second_exercise() -> None:
    assert work_order([2, 3], [1, 1], first={1}) == [[(1, 1), (0, 1), (1, 2), (0, 2), (1, 3)]]
    assert work_order([1, 1, 1, 1], [1, 1, 2, 2], first={2}) == [
        [(0, 1), (1, 1)],
        [(3, 1), (2, 1)],
    ]
