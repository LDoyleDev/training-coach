import pytest

from training_coach.domain.volume import shown, weekly_sets


def test_each_set_counts_its_weight_for_each_muscle() -> None:
    items = [
        ({"lats": 1, "upper back": 0.5, "biceps": 0.5}, 4),
        ({"biceps": 1, "forearms": 0.25}, 3),
        ({}, 1),  # conditioning: no muscles
    ]
    assert weekly_sets(items) == [
        ("biceps", 5),
        ("lats", 4),
        ("upper back", 2),
        ("forearms", 0.75),
    ]


def test_ties_sorted_by_name_and_empty_input() -> None:
    assert weekly_sets([({"quads": 1}, 3), ({"chest": 1}, 3)]) == [("chest", 3), ("quads", 3)]
    assert weekly_sets([]) == []


def test_negative_sets_rejected() -> None:
    with pytest.raises(ValueError, match=">= 0"):
        weekly_sets([({"quads": 1}, -1)])


def test_shown_drops_a_needless_decimal() -> None:
    assert [shown(10.0), shown(7.5), shown(6.25)] == ["10", "7.5", "6.25"]
