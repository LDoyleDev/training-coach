import pytest

from training_coach.domain.enums import Side
from training_coach.domain.progression import Progress, assess, combine_sides, session_met_top
from training_coach.domain.targets import Prescription

PUSH_UPS = Prescription(sets=3, rep_min=10, rep_max=20)
TOP = [20, 20, 20]


@pytest.mark.parametrize(
    ("recent", "has_next", "expected"),
    [
        pytest.param([], True, Progress.HOLD, id="no-history"),
        pytest.param([TOP], True, Progress.HOLD, id="only-one-session"),
        pytest.param([TOP, TOP], True, Progress.READY, id="two-at-top"),
        pytest.param([TOP, TOP], False, Progress.TOP_OF_LADDER, id="no-harder-step"),
        pytest.param([TOP, [20, 20, 19]], True, Progress.HOLD, id="older-session-short"),
        pytest.param([[20, 20, 19], TOP], True, Progress.HOLD, id="latest-short"),
        pytest.param([[20, 20], TOP], True, Progress.HOLD, id="missing-set"),
        pytest.param([TOP, TOP, [10, 10, 10]], True, Progress.READY, id="only-last-two-count"),
        pytest.param([[22, 21, 20], TOP], True, Progress.READY, id="above-top-counts"),
    ],
)
def test_assess(recent: list[list[int]], has_next: bool, expected: Progress) -> None:
    assert assess(PUSH_UPS, recent, has_next_step=has_next) is expected


def test_extra_sets_beyond_plan_do_not_block() -> None:
    assert session_met_top(PUSH_UPS, [20, 20, 20, 8])


def test_combine_sides_takes_weaker_side_per_set() -> None:
    rows = [
        (1, Side.LEFT, 12),
        (1, Side.RIGHT, 10),
        (2, Side.RIGHT, 11),
        (2, Side.LEFT, 11),
        (3, Side.BOTH, 9),
    ]
    assert combine_sides(rows) == [10, 11, 9]


def test_combine_sides_orders_by_set_number() -> None:
    assert combine_sides([(3, Side.BOTH, 7), (1, Side.BOTH, 9), (2, Side.BOTH, 8)]) == [9, 8, 7]
    assert combine_sides([]) == []
