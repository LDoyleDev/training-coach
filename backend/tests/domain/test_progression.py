import pytest

from training_coach.domain.enums import ExerciseKind, Side
from training_coach.domain.progression import Progress, assess, combine_sides, session_met_top
from training_coach.domain.targets import Prescription

PUSH_UPS = Prescription(sets=3, rep_min=10, rep_max=20)
TOP = [20, 20, 20]
DEAD_HANG = Prescription(sets=1, rep_min=30, rep_max=60, kind=ExerciseKind.SECONDS)


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


@pytest.mark.parametrize(
    "recent",
    [
        pytest.param([TOP, TOP], id="two-at-top"),
        pytest.param([TOP, [20, 20, 19]], id="older-session-short"),
        pytest.param([[20, 20], TOP], id="missing-set"),
        pytest.param([TOP, TOP, [10, 10, 10]], id="only-last-two-count"),
    ],
)
def test_sessions_saved_without_a_count_are_judged_as_before(recent: list[list[int]]) -> None:
    unknown: list[int | None] = [None] * len(recent)
    before = assess(PUSH_UPS, recent, has_next_step=True)
    assert assess(PUSH_UPS, recent, has_next_step=True, planned=unknown) is before


# Newest first, with the sets each session planned (ADR-0084). PUSH_UPS: 3 sets of 10-20.
@pytest.mark.parametrize(
    ("item", "recent", "planned", "expected"),
    [
        pytest.param(PUSH_UPS, [TOP, [20, 20]], [3, 2], Progress.READY, id="two-set-day-full-day"),
        pytest.param(PUSH_UPS, [[20, 20], [20, 20]], [2, 2], Progress.READY, id="two-short-days"),
        pytest.param(PUSH_UPS, [TOP, [20, 19]], [3, 2], Progress.HOLD, id="short-day-below-top"),
        pytest.param(PUSH_UPS, [[20], TOP], [2, 3], Progress.HOLD, id="planned-set-missing"),
        pytest.param(PUSH_UPS, [[20, 20, 0], TOP], [2, 3], Progress.READY, id="dropped-not-zero"),
        # A 1-set day doesn't count, either way: the two are the last two that do.
        pytest.param(PUSH_UPS, [[20], TOP], [1, 3], Progress.HOLD, id="one-set-day-not-counted"),
        pytest.param(
            PUSH_UPS, [[20], TOP, TOP], [1, 3, 3], Progress.READY, id="one-set-day-passed-over"
        ),
        pytest.param(
            PUSH_UPS, [[12], TOP, TOP], [1, 3, 3], Progress.READY, id="one-set-day-below-top"
        ),
        pytest.param(PUSH_UPS, [[], TOP, TOP], [0, 3, 3], Progress.READY, id="dropped-for-the-day"),
        # An old session keeps the rule: every set the prescription plans, and it counts.
        pytest.param(PUSH_UPS, [[20, 20], TOP], [2, None], Progress.READY, id="new-then-old"),
        pytest.param(PUSH_UPS, [TOP, [20, 20]], [3, None], Progress.HOLD, id="old-missing-set"),
        pytest.param(
            PUSH_UPS, [TOP, [20, 20, 20, 15]], [3, 4], Progress.HOLD, id="day-planned-more"
        ),
        # A one-set exercise planned as usual counts; dropped for the day, it doesn't.
        pytest.param(DEAD_HANG, [[60], [65]], [1, 1], Progress.READY, id="one-set-prescription"),
        pytest.param(DEAD_HANG, [[60], [60]], [0, 1], Progress.HOLD, id="one-set-dropped"),
        pytest.param(DEAD_HANG, [[60], [45]], [1, None], Progress.HOLD, id="one-set-old-short"),
    ],
)
def test_assess_on_a_shorter_day(
    item: Prescription, recent: list[list[int]], planned: list[int | None], expected: Progress
) -> None:
    assert assess(item, recent, has_next_step=True, planned=planned) is expected


def test_assess_needs_a_count_per_session() -> None:
    with pytest.raises(ValueError, match="1 planned counts for 2 sessions"):
        assess(PUSH_UPS, [TOP, TOP], has_next_step=True, planned=[3])


def test_unilateral_short_day_judges_the_weaker_side_of_its_sets() -> None:
    rows = [
        (1, Side.LEFT, 20),
        (1, Side.RIGHT, 21),
        (2, Side.LEFT, 20),
        (2, Side.RIGHT, 20),
        (3, Side.LEFT, 20),  # past the plan, one side: not a 0
    ]
    values = combine_sides(rows, unilateral=True)
    assert session_met_top(PUSH_UPS, values, planned=2)
    assert not session_met_top(PUSH_UPS, values)  # saved without a count: set 3 is a 0
    weaker = combine_sides([*rows[:3], (2, Side.RIGHT, 19)], unilateral=True)
    assert not session_met_top(PUSH_UPS, weaker, planned=2)


def test_extra_sets_beyond_plan_do_not_block() -> None:
    assert session_met_top(PUSH_UPS, [20, 20, 20, 8])


def test_combine_sides_takes_weaker_side_per_set() -> None:
    rows = [
        (1, Side.LEFT, 12),
        (1, Side.RIGHT, 10),
        (2, Side.RIGHT, 11),
        (2, Side.LEFT, 11),
    ]
    assert combine_sides(rows, unilateral=True) == [10, 11]


def test_combine_sides_orders_by_set_number() -> None:
    rows = [(3, Side.BOTH, 7), (1, Side.BOTH, 9), (2, Side.BOTH, 8)]
    assert combine_sides(rows, unilateral=False) == [9, 8, 7]
    assert combine_sides([], unilateral=False) == []


def test_missing_set_counts_as_zero_and_blocks_progress() -> None:
    rows = [(1, Side.BOTH, 20), (3, Side.BOTH, 20), (4, Side.BOTH, 20)]
    values = combine_sides(rows, unilateral=False)
    assert values == [20, 0, 20, 20]
    assert not session_met_top(PUSH_UPS, values)


def test_missing_side_counts_as_zero_and_blocks_progress() -> None:
    rows = [
        (1, Side.LEFT, 20),
        (1, Side.RIGHT, 20),
        (2, Side.LEFT, 20),
        (3, Side.LEFT, 20),
        (3, Side.RIGHT, 20),
    ]
    values = combine_sides(rows, unilateral=True)
    assert values == [20, 0, 20]
    assert assess(PUSH_UPS, [values, values], has_next_step=True) is Progress.HOLD


def test_set_numbers_start_at_one() -> None:
    with pytest.raises(ValueError, match="start at 1"):
        combine_sides([(0, Side.BOTH, 5)], unilateral=False)
