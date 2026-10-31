import pytest

from training_coach.domain.step_levels import Mark, StepLevel, first_fall


@pytest.mark.parametrize(
    ("levels", "fall"),
    [
        ([], None),
        ([4], None),
        ([2, 3, 3, 4, 6, 6], None),
        ([4, 3], 1),
        ([1, 2, 5, 4, 3], 3),
    ],
)
def test_first_fall_finds_the_first_step_easier_than_the_one_below(
    levels: list[int], fall: int | None
) -> None:
    assert first_fall(levels) == fall


def test_six_levels_and_five_marks() -> None:
    """ADR-0083: 1 Supported to 6 Advanced, and the marks behind the preferences."""
    assert [int(level) for level in StepLevel] == [1, 2, 3, 4, 5, 6]
    assert (StepLevel.SUPPORTED, StepLevel.REGULAR, StepLevel.ADVANCED) == (1, 4, 6)
    assert {str(mark) for mark in Mark} == {"floor", "kneeling", "impact", "hanging", "balance"}
