import pytest

from training_coach.domain.muscles import Kit, Pattern, Stress, parse_need, step_stress


def test_kit_with_and_without_a_weight() -> None:
    assert parse_need("kettlebell:16") == (Kit.KETTLEBELL, 16)
    assert parse_need("pull-up bar") == (Kit.PULL_UP_BAR, None)
    assert parse_need("ab wheel") == (Kit.AB_WHEEL, None)


@pytest.mark.parametrize(
    ("need", "error"),
    [
        ("kettlebell", "say the weight in kg"),
        ("kettlebell:heavy", "say the weight in kg"),
        ("kettlebell:0", "say the weight in kg"),
        ("kettlebell:120", "say the weight in kg"),
        ("pull-up bar:5", "has no weight"),
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
