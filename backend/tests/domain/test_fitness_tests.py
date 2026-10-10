import pytest

from training_coach.domain.enums import Side
from training_coach.domain.fitness_tests import FitnessTest, Result, Unit, problem

TESTS = (
    FitnessTest("max-pull-ups", "Max pull-ups", 1, Unit.REPS, False, "cue"),
    FitnessTest("dead-hang", "Dead hang", 1, Unit.SECONDS, False, "cue"),
    FitnessTest("split-squat", "Split squat", 2, Unit.REPS, True, "cue"),
    FitnessTest("toe-touch", "Toe touch", 2, Unit.CM, False, "cue"),
)


def test_a_day_with_some_tests_skipped_is_fine() -> None:
    assert problem(TESTS, 1, [Result("max-pull-ups", Side.BOTH, 8)]) is None
    both_sides = [Result("split-squat", Side.LEFT, 14), Result("split-squat", Side.RIGHT, 12)]
    assert problem(TESTS, 2, [*both_sides, Result("toe-touch", Side.BOTH, -4)]) is None


@pytest.mark.parametrize(
    ("day", "results", "reason"),
    [
        (3, [Result("max-pull-ups", Side.BOTH, 8)], "no test day 3"),
        (1, [], "every test was skipped"),
        (2, [Result("max-pull-ups", Side.BOTH, 8)], "isn't a day 2 test"),
        (1, [Result("dead-hang", Side.LEFT, 30)], "once, not per side"),
        (2, [Result("split-squat", Side.BOTH, 12)], "per side"),
        (1, [Result("dead-hang", Side.BOTH, 30)] * 2, "in twice"),
        (1, [Result("dead-hang", Side.BOTH, 3601)], "outside 0 to 3600"),
        (2, [Result("toe-touch", Side.BOTH, -61)], "outside -60 to 60"),
        (2, [Result("split-squat", Side.LEFT, 12)], "needs both sides"),
    ],
)
def test_results_that_cant_be_saved_say_why(day: int, results: list[Result], reason: str) -> None:
    found = problem(TESTS, day, results)
    assert found is not None
    assert reason in found
