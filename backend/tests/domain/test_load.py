"""Where each set's weight starts on the set screen (ADR-0072)."""

from training_coach.domain.load import (
    Load,
    LoadKit,
    NextWeight,
    carried,
    kg_text,
    next_weight,
    top_weight,
    valid_kg,
)
from training_coach.domain.targets import Prescription


def test_with_no_history_every_set_starts_at_the_kits_first_weight() -> None:
    assert carried(LoadKit.BARBELL, 3, []) == Load(LoadKit.BARBELL, 2.5, (20.0,) * 3, False)
    assert carried(LoadKit.DUMBBELLS, 2, []).kg == (8.0, 8.0)
    assert carried(LoadKit.MACHINE, 1, []).increment == 5.0


def test_each_set_starts_at_the_same_set_last_time() -> None:
    load = carried(LoadKit.DUMBBELLS, 3, [(1, 16.0), (2, 18.0), (3, 18.0)])
    assert (load.kg, load.carried) == ((16.0, 18.0, 18.0), True)


def test_a_set_not_done_last_time_starts_at_the_nearest_set_before_it() -> None:
    assert carried(LoadKit.BARBELL, 4, [(1, 60.0), (3, 62.5)]).kg == (60.0, 60.0, 62.5, 62.5)


def test_a_first_set_missing_last_time_starts_at_the_first_one_done() -> None:
    assert carried(LoadKit.MACHINE, 2, [(2, 45.0)]).kg == (45.0, 45.0)


def test_a_weight_is_above_nothing_and_within_the_bound() -> None:
    assert [valid_kg(kg) for kg in (0.5, 500, 0, 500.5)] == [True, True, False, False]


def test_weights_read_as_a_person_writes_them() -> None:
    assert (kg_text(20.0), kg_text(22.5)) == ("20", "22.5")


ROWS = Prescription(sets=3, rep_min=8, rep_max=12)


def at(kg: float, sets: int) -> list[tuple[int, float]]:
    return [(n, kg) for n in range(1, sets + 1)]


def test_every_set_at_the_top_suggests_the_next_weight_from_the_bottom() -> None:
    assert next_weight(ROWS, [12, 12, 12], at(20.0, 3), 2.0) == NextWeight(22.0, (8, 8, 8))
    assert next_weight(ROWS, [12, 12, 13, 5], at(60.0, 4), 2.5) == NextWeight(62.5, (8, 8, 8))


def test_a_missed_set_or_no_history_holds_the_weight() -> None:
    assert next_weight(ROWS, [12, 12, 11], at(20.0, 3), 2.0) is None
    assert next_weight(ROWS, [12, 12], at(20.0, 2), 2.0) is None
    assert next_weight(ROWS, None, at(20.0, 3), 2.0) is None
    assert next_weight(ROWS, [12, 12, 12], [], 2.0) is None  # no weight logged
    assert next_weight(ROWS, [12, 12, 12], at(498.0, 3), 5.0) is None  # past the bound


def test_a_session_not_all_at_one_weight_suggests_nothing() -> None:
    """A pyramid, or a set without a weight, is not a session at its heaviest weight."""
    pyramid = [(1, 14.0), (2, 12.0), (3, 12.0)]
    assert next_weight(ROWS, [12, 12, 12], pyramid, 2.0) is None
    assert next_weight(ROWS, [12, 12, 12], [(1, 14.0), (2, 14.0)], 2.0) is None


def test_a_sessions_weight_is_its_heaviest_set() -> None:
    assert top_weight([(1, 20.0), (2, 22.0), (3, 21.0)]) == 22.0
    assert top_weight([]) is None
