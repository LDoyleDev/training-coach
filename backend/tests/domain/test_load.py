"""Where each set's weight starts on the set screen (ADR-0072)."""

from training_coach.domain.kit import Item
from training_coach.domain.load import (
    NO_WEIGHT,
    Increments,
    Load,
    LoadKit,
    NextWeight,
    carried,
    kg_text,
    next_weight,
    owned_weights,
    progressed,
    ready,
    top_weight,
    valid_increment,
    valid_kg,
    weights_text,
)
from training_coach.domain.muscles import Kit
from training_coach.domain.targets import Prescription


def test_with_no_history_every_set_starts_at_the_kits_first_weight() -> None:
    assert carried(LoadKit.BARBELL, 3, []) == Load(LoadKit.BARBELL, 2.5, (20.0,) * 3, False)
    assert carried(LoadKit.DUMBBELLS, 2, []).kg == (8.0, 8.0)
    assert carried(LoadKit.MACHINE, 1, []).increment == 5.0


def test_a_persons_own_increment_replaces_the_kits_default() -> None:
    own = Increments(barbell=1.25, machine=2.5)
    assert [own.of(kit) for kit in LoadKit] == [1.25, 2.0, 2.5, 1.0]  # dumbbells, vest: default
    assert carried(LoadKit.BARBELL, 3, [], own).increment == 1.25
    assert carried(LoadKit.MACHINE, 2, [(1, 40.0)], own).increment == 2.5


def test_an_own_increment_is_in_quarters_of_a_kilo_within_the_bounds() -> None:
    steps = (0.25, 1.25, 20, 0, 0.1, 1.3, 20.25)
    assert [valid_increment(kg) for kg in steps] == [True, True, True, False, False, False, False]


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


def test_weights_follow_a_lines_sets_as_the_confirm_step_writes_them() -> None:
    assert weights_text([16.0, 16.0, 16.0]) == " at 16 kg"
    assert weights_text([16.0, 18.0, None]) == f" at 16 / 18 / {NO_WEIGHT} kg"
    assert weights_text([None, 16.0]) == f" at {NO_WEIGHT} / 16 kg"
    assert weights_text([None, None]) == weights_text([]) == ""


# ------------------------------------------------------------ the weights owned at home


def test_the_dumbbells_owned_are_each_pair_and_an_adjustable_sets_steps() -> None:
    kit = [
        Item(Kit.DUMBBELLS, 16.0),
        Item(Kit.DUMBBELLS, 10.0, min_kg=5.0),  # adjustable, 5-10 kg
        Item(Kit.KETTLEBELL, 24.0),  # not a dumbbell
        Item(Kit.PULL_UP_BAR),
    ]
    assert owned_weights(LoadKit.DUMBBELLS, kit) == (5.0, 7.0, 9.0, 10.0, 16.0)
    own = Increments(dumbbells=2.5)
    assert owned_weights(LoadKit.DUMBBELLS, kit, own) == (5.0, 7.5, 10.0, 16.0)


def test_a_vest_or_backpack_holds_any_weight_from_5_kg_in_the_persons_step() -> None:
    """ADR-0072 (29 Oct 2026): books, bottles or plates, from 5 kg up to what it holds."""
    kit = [Item(Kit.BACKPACK, 8.5), Item(Kit.DUMBBELLS, 12.0)]
    assert owned_weights(LoadKit.BACKPACK, kit) == (5.0, 6.0, 7.0, 8.0, 8.5)
    own = Increments(backpack=2.0)
    assert owned_weights(LoadKit.BACKPACK, kit, own) == (5.0, 7.0, 8.5)
    assert owned_weights(LoadKit.BACKPACK, [Item(Kit.BACKPACK, 3.0)]) == (3.0,)  # under 5 kg
    assert owned_weights(LoadKit.BACKPACK, [Item(Kit.DUMBBELLS, 12.0)]) is None  # none listed
    first = carried(LoadKit.BACKPACK, 4, [])
    assert (first.kg, first.increment) == ((5.0,) * 4, 1.0)  # no history: 5 kg, 1 kg steps
    full = carried(LoadKit.BACKPACK, 3, at(8.5, 3), owned=owned_weights(LoadKit.BACKPACK, kit))
    up = progressed(full, ROWS, [12, 12, 12], at(8.5, 3))
    assert (up.suggested, up.unlock) == (None, "weighted vest or backpack, up to 9.5 kg")


def test_nothing_is_known_owned_without_a_kit_or_for_the_gyms_kit() -> None:
    assert owned_weights(LoadKit.DUMBBELLS, None) is None  # no kit listed yet
    assert owned_weights(LoadKit.BARBELL, [Item(Kit.DUMBBELLS, 10.0)]) is None


def test_a_kit_without_dumbbells_says_nothing_of_the_dumbbells_owned() -> None:
    """A kit listed with no dumbbells keeps the increment rule for - and + and the next weight,
    as at the gym, rather than an unlock note (review of #445)."""
    owned = owned_weights(LoadKit.DUMBBELLS, [Item(Kit.MAT)])
    assert owned is None
    home = carried(LoadKit.DUMBBELLS, 3, at(12.0, 3), owned=owned)
    up = progressed(home, ROWS, [12, 12, 12], at(12.0, 3))
    assert (up.suggested, up.unlock) == (NextWeight(14.0, (8, 8, 8)), None)


def test_at_home_a_first_set_starts_at_the_lightest_weight_owned() -> None:
    load = carried(LoadKit.DUMBBELLS, 2, [], owned=(10.0, 12.0))
    assert (load.kg, load.owned, load.carried) == ((10.0, 10.0), (10.0, 12.0), False)
    assert carried(LoadKit.DUMBBELLS, 1, [(1, 14.0)], owned=(10.0,)).kg == (14.0,)  # carried


def test_ready_is_the_weight_every_set_topped_out_at() -> None:
    assert ready(ROWS, [12, 12, 12], at(20.0, 3)) == 20.0
    assert ready(ROWS, [12, 12, 11], at(20.0, 3)) is None


def test_at_home_the_suggestion_is_the_next_heavier_weight_owned() -> None:
    home = carried(LoadKit.DUMBBELLS, 3, at(12.0, 3), owned=(10.0, 12.0, 16.0, 20.0))
    up = progressed(home, ROWS, [12, 12, 12], at(12.0, 3))
    assert (up.suggested, up.unlock) == (NextWeight(16.0, (8, 8, 8)), None)
    assert progressed(home, ROWS, [12, 12, 11], at(12.0, 3)) == home  # a missed set holds


def test_at_home_owning_none_heavier_names_the_weight_that_would_open_it() -> None:
    home = carried(LoadKit.DUMBBELLS, 3, at(16.0, 3), Increments(dumbbells=2.5), owned=(16.0,))
    up = progressed(home, ROWS, [12, 12, 12], at(16.0, 3))
    assert (up.suggested, up.unlock) == (None, "18.5 kg dumbbells")
    heaviest = carried(LoadKit.DUMBBELLS, 3, at(499.0, 3), owned=(16.0,))
    assert progressed(heaviest, ROWS, [12, 12, 12], at(499.0, 3)) == heaviest  # past the bound


def test_without_owned_weights_the_increment_rule_stands() -> None:
    gym = carried(LoadKit.DUMBBELLS, 3, at(12.0, 3))
    assert progressed(gym, ROWS, [12, 12, 12], at(12.0, 3)).suggested == NextWeight(14.0, (8,) * 3)
