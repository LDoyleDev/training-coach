import pytest

from training_coach.domain.records import NewBests, new_bests


def test_the_first_session_at_a_step_sets_no_record() -> None:
    assert new_bests([12, 12, 12], []) == NewBests()
    assert not new_bests([12, 12, 12], [])


@pytest.mark.parametrize(
    ("current", "earlier", "expected"),
    [
        pytest.param([9, 8, 7], [[8, 8, 8]], NewBests(best_set=9), id="better-set-same-total"),
        pytest.param([8, 8, 9], [[9, 7, 7]], NewBests(total=25), id="better-total-same-set"),
        pytest.param([10, 9], [[8, 8], [9, 7]], NewBests(best_set=10, total=19), id="both"),
        pytest.param([8, 8], [[8, 8]], NewBests(), id="equal-is-not-a-record"),
        pytest.param([7, 7], [[8, 8], [5, 5]], NewBests(), id="beats-only-an-older-one"),
        pytest.param([], [[3]], NewBests(), id="nothing-logged"),
        pytest.param([4], [[]], NewBests(best_set=4, total=4), id="earlier-empty"),
    ],
)
def test_records_must_beat_every_earlier_session(
    current: list[int], earlier: list[list[int]], expected: NewBests
) -> None:
    result = new_bests(current, earlier)
    assert result == expected
    assert bool(result) == (expected != NewBests())
