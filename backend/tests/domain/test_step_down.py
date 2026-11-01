"""The step-down suggestion (ADR-0084): table tests."""

import pytest

from training_coach.domain.enums import ExerciseKind, Side
from training_coach.domain.progression import (
    Catalogued,
    StepDown,
    combine_sides,
    easier_exercises,
    judged_sessions,
    out_of_reach,
    step_down,
)
from training_coach.domain.targets import Pace, Prescription, judged

# 3 sets of 10-20: a step of 2, so a baseline of 5 sets targets of 7.
PUSH_UPS = Prescription(sets=3, rep_min=10, rep_max=20)
LOW = [5, 5, 5]
HANG = Prescription(sets=1, rep_min=30, rep_max=60, kind=ExerciseKind.SECONDS)


# Newest first. The last session in each list is the baseline.
@pytest.mark.parametrize(
    ("recent", "expected"),
    [
        pytest.param([], StepDown.NONE, id="no-history"),
        pytest.param([LOW], StepDown.NONE, id="baseline-only"),
        pytest.param([LOW, LOW], StepDown.NONE, id="baseline-not-counted"),
        pytest.param([LOW, LOW, LOW], StepDown.SUGGEST, id="two-out-of-reach-after-baseline"),
        pytest.param([LOW, LOW, LOW, LOW], StepDown.SUGGEST, id="eased-target-still-missed"),
        pytest.param([LOW, [10, 10, 10], LOW], StepDown.NONE, id="older-one-met"),
        pytest.param([[10, 10, 10], LOW, LOW], StepDown.NONE, id="latest-reached-bottom"),
        # Growing below the range meets its targets: no suggestion.
        pytest.param([[7, 7, 7], [5, 5, 5], [3, 3, 3]], StepDown.NONE, id="growing-below"),
        pytest.param([[8, 8, 8], [7, 7, 7], [5, 5, 5]], StepDown.NONE, id="met-below-bottom"),
        # Most sets: two of three short of target and bottom; one of three is not most.
        pytest.param([[5, 5, 12], [5, 5, 12], LOW], StepDown.SUGGEST, id="two-of-three"),
        pytest.param([[5, 5, 12], [5, 12, 12], LOW], StepDown.NONE, id="one-of-three"),
        # Missed, but in the range: holding a target is ADR-0027's business.
        pytest.param([[10, 10, 10]] * 3, StepDown.NONE, id="missed-in-range"),
        # A missing set takes the weakest logged, as targets read it.
        pytest.param([[5], [5, 5], LOW], StepDown.SUGGEST, id="missing-sets"),
    ],
)
def test_step_down(recent: list[list[int]], expected: StepDown) -> None:
    assert step_down(PUSH_UPS, recent, has_step_below=True) is expected


def test_the_first_step_has_no_step_below() -> None:
    assert step_down(PUSH_UPS, [LOW, LOW, LOW], has_step_below=False) is StepDown.FIRST_STEP
    assert step_down(PUSH_UPS, [LOW, LOW], has_step_below=False) is StepDown.NONE


def test_a_loaded_step_lowers_the_weight_instead() -> None:
    assert step_down(PUSH_UPS, [LOW, LOW, LOW], has_step_below=True, loaded=True) is StepDown.NONE


def test_unilateral_sets_count_the_weaker_side() -> None:
    rows = [
        (n, side, 12 if side is Side.LEFT else 5)
        for n in (1, 2, 3)
        for side in Side
        if side is not Side.BOTH
    ]
    weaker = combine_sides(rows, unilateral=True)
    assert weaker == LOW
    assert step_down(PUSH_UPS, [weaker, weaker, weaker], has_step_below=True) is StepDown.SUGGEST


# Only the sets each day planned (ADR-0084).
@pytest.mark.parametrize(
    ("recent", "planned", "expected"),
    [
        pytest.param([[5, 12, 12]] * 2 + [LOW], [None, None, 3], StepDown.NONE, id="all-planned"),
        pytest.param([[5, 12, 12]] * 2 + [LOW], [1, 1, 3], StepDown.SUGGEST, id="one-planned"),
        pytest.param([[5, 5], [5, 5], LOW], [2, 2, 3], StepDown.SUGGEST, id="short-days"),
        pytest.param([[5], [5], LOW], [0, 0, 3], StepDown.NONE, id="none-planned"),
    ],
)
def test_only_the_planned_sets_count(
    recent: list[list[int]], planned: list[int | None], expected: StepDown
) -> None:
    found = step_down(PUSH_UPS, recent, has_step_below=True, planned=planned)
    assert found is expected


@pytest.mark.parametrize(
    ("skipped", "expected"),
    [
        pytest.param([False, False, False, False], StepDown.SUGGEST, id="none-skipped"),
        pytest.param([True, False, False, False], StepDown.SUGGEST, id="newest-passed-over"),
        pytest.param([False, True, True, False], StepDown.NONE, id="only-one-left"),
        pytest.param([True, True, False, False], StepDown.NONE, id="baseline-never-counts"),
    ],
)
def test_strength_block_and_for_today_sessions_are_skipped(
    skipped: list[bool], expected: StepDown
) -> None:
    found = step_down(PUSH_UPS, [LOW] * 4, has_step_below=True, skipped=skipped)
    assert found is expected


def test_targets_follow_the_pace() -> None:
    # Steady: +1, so 5 then 6 meets its target; fast: +2 misses it.
    recent = [[6, 6, 6], [6, 6, 6], LOW]
    assert step_down(PUSH_UPS, recent, has_step_below=True, pace=Pace.STEADY) is StepDown.NONE
    assert step_down(PUSH_UPS, recent, has_step_below=True, pace=Pace.FAST) is StepDown.SUGGEST


def test_timed_exercises() -> None:
    assert step_down(HANG, [[15], [15], [15]], has_step_below=True) is StepDown.SUGGEST


def test_judged_sessions() -> None:
    assert judged_sessions(0) == []
    assert judged_sessions(3) == [0, 1]
    assert judged_sessions(3, [False, True, False]) == [0]
    with pytest.raises(ValueError, match="skip flags"):
        judged_sessions(2, [False])


def test_judged_gives_each_sessions_targets_newest_first() -> None:
    assert judged(PUSH_UPS, [LOW, LOW]) == [((7, 7, 7), (5, 5, 5)), ((5, 5, 5), (5, 5, 5))]
    assert judged(PUSH_UPS, [[25]]) == [((20, 20, 20), (20, 20, 20))]


def test_out_of_reach() -> None:
    assert out_of_reach(PUSH_UPS, (7, 7, 7), (5, 5, 6))
    assert not out_of_reach(PUSH_UPS, (5, 5, 5), (5, 5, 5))
    assert not out_of_reach(PUSH_UPS, (), ())


def test_easier_exercises_share_a_prime_mover_and_start_low() -> None:
    catalogue = [
        Catalogued("Wall push-up", frozenset({"chest", "triceps"}), 1),
        Catalogued("Incline push-up", frozenset({"chest"}), 2),
        Catalogued("Dips", frozenset({"chest"}), 4),
        Catalogued("Squat", frozenset({"quads"}), 1),
        Catalogued("Untested", frozenset({"chest"}), None),
    ]
    found = easier_exercises(frozenset({"chest"}), catalogue)
    assert found == ["Wall push-up", "Incline push-up"]
    assert easier_exercises(frozenset(), catalogue) == []


def test_a_last_set_to_failure_is_read_as_the_targets_read_it() -> None:
    """At or above its target it counts as met (ADR-0084); below the range and short, it isn't."""
    recent = [[5, 5, 5], [5, 5, 5], LOW]
    assert step_down(PUSH_UPS, recent, has_step_below=True, failure_sets=[3, 3, None]) is (
        StepDown.SUGGEST
    )
    met = [[5, 5, 25], [5, 5, 25], LOW]  # two of three still short: most
    found = step_down(PUSH_UPS, met, has_step_below=True, failure_sets=[3, 3, None])
    assert found is StepDown.SUGGEST
    one = [[5, 25, 25], [5, 25, 25], LOW]
    assert step_down(PUSH_UPS, one, has_step_below=True, failure_sets=[3, 3, None]) is StepDown.NONE
