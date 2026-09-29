import pytest

from training_coach.domain.targets import Prescription, targets

PULL_UPS = Prescription(sets=4, rep_min=5, rep_max=12)


@pytest.mark.parametrize(
    ("last", "expected"),
    [
        pytest.param(None, (5, 5, 5, 5), id="no-history"),
        pytest.param([], (5, 5, 5, 5), id="empty-history"),
        pytest.param([8, 7, 6, 5], (8, 8, 7, 6), id="spec-example"),
        pytest.param([8, 8, 8, 8], (9, 9, 9, 9), id="all-equal-plus-one"),
        pytest.param([12, 12, 12, 12], (12, 12, 12, 12), id="capped-at-top"),
        pytest.param([12, 11, 12, 10], (12, 12, 12, 11), id="catch-up-to-best"),
        pytest.param([3, 2, 2, 1], (3, 3, 3, 2), id="below-range-grows-gradually"),
        pytest.param([0, 0, 0, 0], (1, 1, 1, 1), id="from-zero"),
        pytest.param([15, 9, 9, 9], (12, 10, 10, 10), id="above-range-clamped"),
        pytest.param([8, 7], (8, 8, 8, 8), id="missing-sets-padded"),
        pytest.param([8, 7, 6, 5, 4, 3], (8, 8, 7, 6), id="extra-sets-ignored"),
    ],
)
def test_targets(last: list[int] | None, expected: tuple[int, ...]) -> None:
    assert targets(PULL_UPS, last) == expected


def test_fixed_rep_count() -> None:
    swings = Prescription(sets=4, rep_min=20, rep_max=20)
    assert targets(swings, [20, 18, 20, 15]) == (20, 19, 20, 16)
    assert targets(swings, [20, 20, 20, 20]) == (20, 20, 20, 20)


def test_duration_in_minutes() -> None:
    zone2 = Prescription(sets=1, rep_min=45, rep_max=60)
    assert targets(zone2, [50]) == (51,)


@pytest.mark.parametrize(
    ("sets", "rep_min", "rep_max"),
    [(0, 5, 12), (3, 0, 12), (3, 10, 5)],
    ids=["sets", "min", "range"],
)
def test_invalid_prescription(sets: int, rep_min: int, rep_max: int) -> None:
    with pytest.raises(ValueError, match="invalid prescription"):
        Prescription(sets=sets, rep_min=rep_min, rep_max=rep_max)
