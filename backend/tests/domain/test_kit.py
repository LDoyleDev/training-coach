import pytest

from training_coach.domain.kit import (
    Item,
    Resistance,
    label,
    missing,
    need_label,
    next_open,
    parse_item,
    problem,
    problems,
    unlocked,
    unlocks_next,
)
from training_coach.domain.muscles import Kit

KB8 = Item(Kit.KETTLEBELL, kg=8)
KB16 = Item(Kit.KETTLEBELL, kg=16)
BAR = Item(Kit.PULL_UP_BAR)
# The swing ladder as it is today: two 8 kg steps, then one for a 16 kg bell.
SWINGS = [["kettlebell:8"], ["kettlebell:8"], ["kettlebell:16"]]


def test_an_unlisted_kit_locks_nothing() -> None:
    assert missing(None, ["kettlebell:16", "pull-up bar"]) == []
    assert next_open(SWINGS, 1, None) == 2


def test_a_kettlebell_must_be_that_exact_weight() -> None:
    assert missing([KB8], ["kettlebell:8"]) == []
    assert missing([KB8], ["kettlebell:16"]) == ["a 16 kg kettlebell"]
    assert missing([KB16], ["kettlebell:8"]) == ["an 8 kg kettlebell"]
    assert missing([KB8, KB16], ["kettlebell:8", "kettlebell:16"]) == []


def test_dumbbells_fixed_pairs_and_adjustable_ranges() -> None:
    pair = Item(Kit.DUMBBELLS, kg=12)
    adjustable = Item(Kit.DUMBBELLS, kg=24, min_kg=2)
    assert missing([pair], ["dumbbells:12"]) == []
    assert missing([pair], ["dumbbells:14"]) == ["14 kg dumbbells"]
    assert missing([adjustable], ["dumbbells:14"]) == []
    assert missing([adjustable], ["dumbbells:30"]) == ["30 kg dumbbells"]
    assert missing([pair], ["dumbbells"]) == []  # any dumbbells


def test_a_vest_or_backpack_loads_up_to_its_weight() -> None:
    vest = Item(Kit.BACKPACK, kg=10)
    assert missing([vest], ["backpack"]) == []
    assert missing([vest], ["backpack:10"]) == []
    assert missing([vest], ["backpack:15"]) == ["a weighted vest or backpack of 15 kg"]
    assert missing([], ["backpack"]) == ["a weighted vest or backpack"]


def test_other_kit_is_there_or_not() -> None:
    band = Item(Kit.BAND, resistance=Resistance.LIGHT)
    assert missing([band, BAR], ["band", "pull-up bar"]) == []
    assert missing([band], ["band", "pull-up bar"]) == ["a pull-up bar"]
    assert need_label("rings") == "rings"
    assert need_label("box") == "a step or box"
    assert need_label("ab wheel") == "an ab wheel"
    assert need_label("kettlebell:18") == "an 18 kg kettlebell"


def test_a_band_step_takes_that_strength_or_a_stronger_one() -> None:
    medium = Item(Kit.BAND, resistance=Resistance.MEDIUM)
    assert missing([medium], ["band:light"]) == []
    assert missing([medium], ["band:medium"]) == []
    assert missing([medium], ["band:heavy"]) == ["a heavy band"]
    assert missing([Item(Kit.MAT)], ["band:light"]) == ["a light band"]


def test_move_up_skips_locked_steps() -> None:
    ladder = [[], ["kettlebell:16"], ["pull-up bar"], ["kettlebell:16"]]
    assert next_open(ladder, 0, [BAR]) == 2
    assert next_open(ladder, 2, [BAR]) is None
    assert next_open(ladder, 0, [BAR, KB16]) == 1


def test_top_for_your_kit_names_what_opens_the_next_step() -> None:
    assert unlocks_next(SWINGS, 1, [KB8]) == ["a 16 kg kettlebell"]
    assert unlocks_next(SWINGS, 0, [KB8]) is None  # a harder open step remains
    assert unlocks_next(SWINGS, 2, [KB8]) is None  # the real top
    assert unlocks_next(SWINGS, 1, None) is None  # no kit listed: nothing locks


def test_what_an_item_would_unlock() -> None:
    ladders = {
        "Kettlebell swing": [("Two-hand, 8 kg", ["kettlebell:8"]), ("Heavier", ["kettlebell:16"])],
        "Pull-up": [("Strict", ["pull-up bar"]), ("Weighted", ["pull-up bar", "backpack"])],
        "Push-up": [("Push-up", [])],
    }
    assert unlocked(ladders, [KB8, BAR], KB16) == [("Kettlebell swing", "Heavier")]
    assert unlocked(ladders, [KB8], Item(Kit.BACKPACK, kg=10)) == []  # still needs the bar
    assert unlocked(ladders, [KB8, BAR], Item(Kit.BACKPACK, kg=10)) == [("Pull-up", "Weighted")]
    assert unlocked(ladders, None, KB8) == [("Kettlebell swing", "Two-hand, 8 kg")]


def test_labels() -> None:
    assert label(KB16) == "16 kg kettlebell"
    assert label(Item(Kit.DUMBBELLS, kg=12.5)) == "12.5 kg dumbbells"
    assert label(Item(Kit.DUMBBELLS, kg=24, min_kg=2)) == "adjustable dumbbells, 2-24 kg"
    assert label(Item(Kit.BACKPACK, kg=10)) == "weighted vest or backpack, up to 10 kg"
    assert label(Item(Kit.BAND, resistance=Resistance.HEAVY)) == "heavy band"
    assert label(Item(Kit.BENCH, note="two stools")) == "bench, stools or bed to lie on"


@pytest.mark.parametrize(
    ("token", "item"),
    [
        ("kettlebell:16", KB16),
        ("dumbbells:12", Item(Kit.DUMBBELLS, kg=12)),
        ("dumbbells:2-24", Item(Kit.DUMBBELLS, kg=24, min_kg=2)),
        ("backpack:10", Item(Kit.BACKPACK, kg=10)),
        ("band:light", Item(Kit.BAND, resistance=Resistance.LIGHT)),
        ("pull-up bar", BAR),
    ],
)
def test_parse_an_item(token: str, item: Item) -> None:
    assert parse_item(token) == item


@pytest.mark.parametrize(
    ("token", "error"),
    [
        ("kettlebell", "say the weight"),
        ("kettlebell:heavy", "could not convert"),
        ("band", "is not a valid Resistance"),
        ("pull-up bar:5", "has no weight"),
        ("dumbbells:24-2", "a range goes"),
        ("sofa", "is not a valid Kit"),
    ],
)
def test_bad_tokens_are_refused(token: str, error: str) -> None:
    with pytest.raises(ValueError, match=error):
        parse_item(token)


@pytest.mark.parametrize(
    ("item", "error"),
    [
        (Item(Kit.KETTLEBELL), "say the weight"),
        (Item(Kit.MAT, kg=2), "has no weight"),
        (Item(Kit.KETTLEBELL, kg=0), "from 0.5 to 100"),
        (Item(Kit.KETTLEBELL, kg=16.3), "in steps of 0.5"),
        (Item(Kit.KETTLEBELL, kg=16, min_kg=8), "a range goes"),
        (Item(Kit.DUMBBELLS, kg=10, min_kg=-1), "from 0.5 to 100"),
        (Item(Kit.BAND), "light, medium or heavy"),
        (Item(Kit.MAT, resistance=Resistance.LIGHT), "has no strength"),
        (Item(Kit.BENCH, note="x" * 41), "40 characters"),
    ],
)
def test_bad_items_are_refused(item: Item, error: str) -> None:
    found = problem(item)
    assert found is not None
    assert error in found


def test_a_kit_is_refused_for_a_bad_item_a_repeat_or_its_size() -> None:
    assert problems([KB8, KB16, BAR, Item(Kit.BENCH, note="two stools")]) is None
    assert problems([KB8, Item(Kit.KETTLEBELL, kg=8, note="the old one")]) == (
        "8 kg kettlebell is listed twice"
    )
    assert problems([Item(Kit.MAT, kg=1)]) == "mat has no weight"
    assert problems([Item(Kit.KETTLEBELL, kg=n / 2) for n in range(1, 62)]) == "at most 60 items"
