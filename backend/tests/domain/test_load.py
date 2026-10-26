"""Where each set's weight starts on the set screen (ADR-0072)."""

from training_coach.domain.load import Load, LoadKit, carried, kg_text, valid_kg


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
    assert valid_kg(0.5) and valid_kg(500)
    assert not valid_kg(0) and not valid_kg(500.5)


def test_weights_read_as_a_person_writes_them() -> None:
    assert (kg_text(20.0), kg_text(22.5)) == ("20", "22.5")
