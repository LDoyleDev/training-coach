import pytest

from training_coach.domain.muscles import (
    Kit,
    Muscle,
    Pattern,
    Stress,
    parse_need,
    ranked,
    step_stress,
)


def test_kit_with_and_without_a_weight() -> None:
    assert parse_need("kettlebell:16") == (Kit.KETTLEBELL, 16)
    assert parse_need("pull-up bar") == (Kit.PULL_UP_BAR, None)
    assert parse_need("ab wheel") == (Kit.AB_WHEEL, None)
    assert parse_need("backpack") == (Kit.BACKPACK, None)  # any load
    assert parse_need("backpack:10") == (Kit.BACKPACK, 10)
    assert parse_need("dumbbells:12") == (Kit.DUMBBELLS, 12)


@pytest.mark.parametrize(
    ("need", "error"),
    [
        ("kettlebell", "say the weight in kg"),
        ("kettlebell:heavy", "say the weight in kg"),
        ("kettlebell:0", "say the weight in kg"),
        ("kettlebell:120", "say the weight in kg"),
        ("pull-up bar:5", "has no weight"),
        ("dumbbells:", "say the weight in kg"),
        ("sofa", "is not a valid Kit"),
    ],
)
def test_bad_needs_are_refused(need: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        parse_need(need)


def test_only_loaded_squats_load_the_spine() -> None:
    spine = [Stress.SPINE]
    assert step_stress(spine, Pattern.LUNGE, ["kettlebell:8"]) == {Stress.SPINE}
    assert step_stress(spine, Pattern.SQUAT, ["backpack"]) == {Stress.SPINE}
    assert step_stress(spine, Pattern.SQUAT, []) == set()
    assert step_stress(spine, Pattern.HINGE, []) == {Stress.SPINE}  # a hinge always does
    assert step_stress([Stress.GRIP], Pattern.VERTICAL_PULL, ["pull-up bar"]) == {Stress.GRIP}


def test_muscles_rank_by_weight_then_the_fixed_order() -> None:
    worked = {Muscle.FOREARMS: 0.25, Muscle.UPPER_BACK: 0.5, Muscle.LATS: 1, Muscle.BICEPS: 0.5}
    assert ranked(worked) == [
        (Muscle.LATS, 1),
        (Muscle.UPPER_BACK, 0.5),
        (Muscle.BICEPS, 0.5),
        (Muscle.FOREARMS, 0.25),
    ]
    assert ranked({}) == []
