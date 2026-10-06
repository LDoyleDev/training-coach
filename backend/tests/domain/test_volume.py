import pytest

from training_coach.domain.volume import weekly_sets


def test_counts_every_listed_group_and_skips_qualities() -> None:
    items = [
        (["lats", "upper back", "biceps"], 4),
        (["biceps"], 3),
        (["conditioning"], 1),
        (["upper back", "posture"], 2),
    ]
    assert weekly_sets(items) == [("biceps", 7), ("upper back", 6), ("lats", 4)]


def test_ties_sorted_by_name_and_empty_input() -> None:
    assert weekly_sets([(["quads"], 3), (["chest"], 3)]) == [("chest", 3), ("quads", 3)]
    assert weekly_sets([]) == []


def test_negative_sets_rejected() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        weekly_sets([(["quads"], -1)])
