"""Rest after each set (ADR-0065)."""

from training_coach.domain.muscles import Muscle, Pattern
from training_coach.domain.rest import Kind, Rest, after_pair, rests, straight
from training_coach.domain.work_order import work_order

SQUAT = Kind(Pattern.SQUAT, frozenset({Muscle.QUADS, Muscle.GLUTES}))
HINGE = Kind(Pattern.HINGE, frozenset({Muscle.HAMSTRINGS}), frozenset({Muscle.GLUTES}))
CURL = Kind(Pattern.ISOLATION, frozenset({Muscle.HAMSTRINGS}))
NECK_FLEXION = Kind(Pattern.ISOLATION, frozenset({Muscle.NECK}))
NECK_EXTENSION = Kind(Pattern.ISOLATION, frozenset({Muscle.NECK}))
ROW = Kind(Pattern.HORIZONTAL_PULL, frozenset({Muscle.LATS, Muscle.UPPER_BACK}))
PUSH = Kind(Pattern.HORIZONTAL_PUSH, frozenset({Muscle.CHEST}))
CALF = Kind(Pattern.ISOLATION, frozenset({Muscle.CALVES}))


def test_a_pair_switches_then_rests_after_the_round() -> None:
    groups = work_order([2, 2], [1, 1])
    assert rests(groups, [ROW, PUSH]) == [
        Rest(15, switch=True),
        Rest(60),
        Rest(15, switch=True),
        Rest(0),
    ]


def test_a_pair_sharing_a_prime_mover_rests_longer() -> None:
    """Pistol squat (glutes 1) + single-leg RDL (glutes 0.5): one counts fully, one half."""
    groups = work_order([2, 2, 1], [1, 1, None])
    assert [r.seconds for r in rests(groups, [SQUAT, HINGE, CALF])] == [15, 90, 15, 90, 0]


def test_a_pair_on_different_muscles_does_not_share() -> None:
    assert after_pair(SQUAT, CURL) == 60
    assert after_pair(HINGE, CURL) == 90  # both count fully for the hamstrings


def test_a_neck_pair_is_opposing_not_shared() -> None:
    assert after_pair(NECK_FLEXION, NECK_EXTENSION) == 60


def test_the_longer_exercise_of_a_pair_rests_as_a_straight_set() -> None:
    groups = work_order([3, 1, 1], [1, 1, None])  # A1 B1 A2 A3, then C1
    assert [r.seconds for r in rests(groups, [ROW, CALF, CALF])] == [15, 60, 90, 90, 0]


def test_straight_sets_rest_by_exercise() -> None:
    groups = work_order([2, 2], [None, None])
    assert [r.seconds for r in rests(groups, [PUSH, CALF])] == [90, 90, 60, 0]


def test_an_exercise_the_catalogue_does_not_know_is_small() -> None:
    assert straight(None) == 60
    assert after_pair(None, ROW) == 60
    assert rests(work_order([2], [None]), [None]) == [Rest(60), Rest(0)]


def test_a_pair_started_with_its_second_exercise_rests_the_same() -> None:
    groups = work_order([2, 2], [1, 1], first={1})
    assert rests(groups, [ROW, PUSH]) == rests(work_order([2, 2], [1, 1]), [ROW, PUSH])


def test_nothing_to_rest_in_an_empty_session() -> None:
    assert rests([], []) == []


def test_a_pair_whose_partner_is_dropped_rests_as_straight_sets() -> None:
    """A trimmed day's 0-set partner (ADR-0082): no switch, the compound's own rest."""
    groups = work_order([2, 0, 1], [1, 1, None])
    assert rests(groups, [SQUAT, CALF, CALF]) == [Rest(90), Rest(90), Rest(0)]
