"""Why a step is locked (ADR-0071, ADR-0083): kit not listed, or a mark the person avoids."""

from training_coach.domain.kit import Item
from training_coach.domain.locks import (
    AVOIDABLE,
    Asks,
    Limits,
    Lock,
    lock,
    next_open,
    unlocks_next,
    warning,
)
from training_coach.domain.muscles import Kit
from training_coach.domain.step_levels import Mark

KB8 = Item(Kit.KETTLEBELL, kg=8)
KB16 = Item(Kit.KETTLEBELL, kg=16)
BAR = Item(Kit.PULL_UP_BAR)
# The swing ladder as it is today: two 8 kg steps, then one for a 16 kg bell.
SWINGS = [Asks(["kettlebell:8"]), Asks(["kettlebell:8"]), Asks(["kettlebell:16"])]
FLOOR = "needs the floor — you've chosen to keep off it"
OFF_THE_FLOOR = Limits(avoid=frozenset({Mark.FLOOR}))


def test_four_marks_can_be_avoided_and_balance_is_not_one() -> None:
    """ADR-0083: four preferences; balance marks a fall risk and has no switch."""
    assert AVOIDABLE == (Mark.FLOOR, Mark.KNEELING, Mark.IMPACT, Mark.HANGING)


def test_nothing_listed_and_nothing_avoided_locks_nothing() -> None:
    found = lock(Asks(["kettlebell:16"], [Mark.FLOOR, Mark.HANGING]), Limits())
    assert found == Lock()
    assert found.open
    assert next_open(SWINGS, 1, Limits()) == 2


def test_a_mark_the_person_avoids_locks_the_step_in_words() -> None:
    found = lock(Asks(marks=[Mark.FLOOR, Mark.BALANCE]), OFF_THE_FLOOR)
    assert (found.missing, found.avoided, found.open) == ((), (FLOOR,), False)
    # A mark nobody avoids, or one the step doesn't have, locks nothing.
    assert lock(Asks(marks=[Mark.BALANCE]), OFF_THE_FLOOR).open
    assert lock(Asks(marks=[Mark.FLOOR]), Limits(avoid=frozenset({Mark.HANGING}))).open


def test_every_avoidable_mark_has_its_reason() -> None:
    every = Limits(avoid=frozenset(AVOIDABLE))
    assert lock(Asks(marks=list(Mark)), every).avoided == (
        FLOOR,
        "needs kneeling — you've chosen not to kneel",
        "needs jumping or running — you've chosen not to jump or run",
        "needs hanging from a bar — you've chosen not to hang",
    )


def test_kit_and_marks_lock_together() -> None:
    both = Limits(kit=[KB8], avoid=frozenset({Mark.FLOOR}))
    found = lock(Asks(["kettlebell:16"], [Mark.FLOOR]), both)
    assert found.missing == ("a 16 kg kettlebell",)
    assert found.avoided == (FLOOR,)
    assert found.reasons() == ["needs a 16 kg kettlebell, not in your kit", FLOOR]
    assert warning("One-arm, 16 kg", found) == (
        "One-arm, 16 kg needs a 16 kg kettlebell, not in your kit; " + FLOOR + "."
    )


def test_a_warning_says_the_one_reason_and_nothing_when_open() -> None:
    assert warning("Standard", lock(Asks(marks=[Mark.FLOOR]), OFF_THE_FLOOR)) == (
        "Standard needs the floor — you've chosen to keep off it."
    )
    assert warning("Two-hand, 16 kg", lock(Asks(["kettlebell:16"]), Limits(kit=[KB8]))) == (
        "Two-hand, 16 kg needs a 16 kg kettlebell, not in your kit."
    )
    assert warning("Wall push-up", lock(Asks(), OFF_THE_FLOOR)) is None


def test_move_up_skips_locked_steps() -> None:
    ladder = [Asks(), Asks(["kettlebell:16"]), Asks(["pull-up bar"]), Asks(["kettlebell:16"])]
    assert next_open(ladder, 0, Limits(kit=[BAR])) == 2
    assert next_open(ladder, 2, Limits(kit=[BAR])) is None
    assert next_open(ladder, 0, Limits(kit=[BAR, KB16])) == 1


def test_move_up_skips_a_marked_step_and_a_kit_locked_one() -> None:
    ladder = [
        Asks(),
        Asks(marks=[Mark.KNEELING]),
        Asks(["pull-up bar"]),
        Asks(marks=[Mark.BALANCE]),
    ]
    no_kneeling = Limits(kit=[], avoid=frozenset({Mark.KNEELING}))
    assert next_open(ladder, 0, no_kneeling) == 3
    assert next_open(ladder, 3, no_kneeling) is None
    assert next_open(ladder, 0, Limits(avoid=frozenset({Mark.KNEELING}))) == 2  # no kit listed


def test_top_for_your_kit_names_what_opens_the_next_step() -> None:
    assert unlocks_next(SWINGS, 1, Limits(kit=[KB8])) == (2, ["a 16 kg kettlebell"])
    assert unlocks_next(SWINGS, 0, Limits(kit=[KB8])) is None  # a harder open step remains
    assert unlocks_next(SWINGS, 2, Limits(kit=[KB8])) is None  # the real top
    assert unlocks_next(SWINGS, 1, Limits()) is None  # no kit listed: nothing locks


def test_kit_unlocks_the_first_step_above_that_isnt_avoided() -> None:
    """No kit opens a step the person avoids, so the kit named is the next one's that only
    lacks kit; with every harder step avoided, nothing is named."""
    ladder = [Asks(), Asks(marks=[Mark.FLOOR]), Asks(["kettlebell:16"]), Asks(["box"])]
    limits = Limits(kit=[KB8], avoid=frozenset({Mark.FLOOR}))
    assert unlocks_next(ladder, 0, limits) == (2, ["a 16 kg kettlebell"])
    floor_only = [Asks(), Asks(["kettlebell:16"], [Mark.FLOOR]), Asks(marks=[Mark.FLOOR])]
    assert unlocks_next(floor_only, 0, limits) is None
