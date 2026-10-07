"""Targets (ADR-0027): a step of about 10% of the range; a miss holds; two misses ease."""

import pytest

from training_coach.domain.enums import ExerciseKind
from training_coach.domain.targets import Prescription, step, targets

PULL_UPS = Prescription(sets=4, rep_min=5, rep_max=12)  # step 1
DIPS = Prescription(sets=3, rep_min=8, rep_max=15)  # step 2
TIBIALIS = Prescription(sets=3, rep_min=15, rep_max=25)  # step 3


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        pytest.param(Prescription(3, 4, 8), 1, id="4-8"),
        pytest.param(PULL_UPS, 1, id="5-12"),
        pytest.param(DIPS, 2, id="8-15-half-rounds-up"),
        pytest.param(Prescription(3, 10, 20), 2, id="10-20"),
        pytest.param(TIBIALIS, 3, id="15-25-half-rounds-up"),
        pytest.param(Prescription(1, 1, 1), 1, id="at-least-one"),
        pytest.param(Prescription(3, 20, 30, ExerciseKind.SECONDS), 5, id="seconds-at-least-5"),
        pytest.param(Prescription(3, 20, 60, ExerciseKind.SECONDS), 5, id="seconds-60"),
        pytest.param(Prescription(3, 30, 90, ExerciseKind.SECONDS), 10, id="seconds-90"),
        pytest.param(Prescription(3, 60, 120, ExerciseKind.SECONDS), 10, id="seconds-120"),
        pytest.param(Prescription(1, 30, 40, ExerciseKind.DURATION_MIN), 1, id="minutes"),
    ],
)
def test_step_is_about_ten_percent_of_the_top(item: Prescription, expected: int) -> None:
    assert step(item) == expected


@pytest.mark.parametrize(
    ("item", "history", "expected"),
    [
        pytest.param(PULL_UPS, [], (5, 5, 5, 5), id="no-history-bottom-of-range"),
        pytest.param(PULL_UPS, [[8, 7, 6, 5]], (9, 8, 7, 6), id="spec-example"),
        pytest.param(DIPS, [[10, 9, 8]], (12, 11, 10), id="step-two"),
        pytest.param(TIBIALIS, [[18, 16, 15]], (21, 19, 18), id="step-three"),
        pytest.param(PULL_UPS, [[12, 12, 12, 12]], (12, 12, 12, 12), id="capped-at-top"),
        pytest.param(PULL_UPS, [[11, 12, 15, 9]], (12, 12, 12, 10), id="above-top-clamped"),
        pytest.param(PULL_UPS, [[8, 7]], (9, 8, 8, 8), id="missing-sets-start-from-weakest"),
        pytest.param(PULL_UPS, [[8, 7, 6, 5, 4, 3]], (9, 8, 7, 6), id="extra-sets-ignored"),
        pytest.param(PULL_UPS, [[]], (1, 1, 1, 1), id="empty-first-session-starts-from-zero"),
        # Newest first: the second session aimed 9/8/7/6 and hit only the first two sets.
        pytest.param(
            PULL_UPS, [[9, 8, 6, 5], [8, 7, 6, 5]], (10, 9, 7, 6), id="a-miss-holds-the-target"
        ),
        # Missed set 3 twice at the same target 7: it eases to last value + 1.
        pytest.param(
            PULL_UPS,
            [[10, 9, 5, 7], [9, 8, 6, 6], [8, 7, 6, 5]],
            (11, 10, 6, 8),
            id="two-misses-ease",
        ),
        # A first session below the bottom is the baseline: targets grow from it, no jump.
        pytest.param(PULL_UPS, [[3, 2, 2, 1]], (4, 3, 3, 2), id="below-range-first-is-baseline"),
        pytest.param(
            PULL_UPS, [[3, 3, 2, 1], [3, 2, 2, 1]], (4, 4, 3, 2), id="below-range-miss-holds"
        ),
        pytest.param(
            PULL_UPS,
            [[4, 4, 3, 2], [3, 3, 2, 1], [3, 2, 2, 1]],
            (5, 5, 4, 3),
            id="below-range-hit-grows-by-step",
        ),
    ],
)
def test_targets(item: Prescription, history: list[list[int]], expected: tuple[int, ...]) -> None:
    assert targets(item, history) == expected


def test_fixed_rep_count() -> None:
    swings = Prescription(sets=4, rep_min=20, rep_max=20)
    assert targets(swings, [[20, 18, 20, 15]]) == (20, 20, 20, 17)  # baseline + 2, capped
    assert targets(swings, [[20, 18, 20, 15], [20, 18, 20, 15]]) == (20, 20, 20, 17)  # held
    assert targets(swings, [[20, 18, 20, 15]] * 3) == (20, 19, 20, 16)  # two misses ease


def test_timed_and_duration_steps() -> None:
    plank = Prescription(sets=2, rep_min=20, rep_max=60, kind=ExerciseKind.SECONDS)
    assert targets(plank, [[40, 35]]) == (45, 40)
    zone2 = Prescription(sets=1, rep_min=30, rep_max=40, kind=ExerciseKind.DURATION_MIN)
    assert targets(zone2, [[32]]) == (33,)


@pytest.mark.parametrize(
    ("sets", "rep_min", "rep_max"),
    [(0, 5, 12), (3, 0, 12), (3, 10, 5)],
    ids=["sets", "min", "range"],
)
def test_invalid_prescription(sets: int, rep_min: int, rep_max: int) -> None:
    with pytest.raises(ValueError, match="invalid prescription"):
        Prescription(sets=sets, rep_min=rep_min, rep_max=rep_max)
