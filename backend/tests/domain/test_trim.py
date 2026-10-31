"""A session trimmed to fit the minutes (ADR-0082)."""

from collections.abc import Sequence
from dataclasses import replace

import pytest

from training_coach.domain.muscles import Muscle, Pattern
from training_coach.domain.trim import Estimate, Item, WarmUp, trim, warm_up

SQUAT = Item(4, Pattern.SQUAT, frozenset({Muscle.QUADS, Muscle.GLUTES}))
HINGE = Item(3, Pattern.HINGE, frozenset({Muscle.HAMSTRINGS, Muscle.GLUTES}))
CURL = Item(3, Pattern.ISOLATION, frozenset({Muscle.HAMSTRINGS}))
CALF = Item(3, Pattern.ISOLATION, frozenset({Muscle.CALVES}))
ROW = Item(2, Pattern.HORIZONTAL_PULL, frozenset({Muscle.LATS, Muscle.UPPER_BACK}))
PULLDOWN = Item(2, Pattern.VERTICAL_PULL, frozenset({Muscle.LATS}))
PUSH = Item(2, Pattern.HORIZONTAL_PUSH, frozenset({Muscle.CHEST}))
CARRY = Item(2, Pattern.CARRY, frozenset({Muscle.FOREARMS}))
ROLLOUT = Item(3, Pattern.CORE, frozenset({Muscle.ABS}))
MOBILITY = Item(1, Pattern.MOBILITY, minutes=10)
RUN = Item(1, Pattern.CARDIO, minutes=30)


def per_set(minutes: float = 5) -> Estimate:
    """A plain estimate: each set ``minutes`` with its rest, a duration item its own minutes."""

    def estimate(counts: Sequence[int], durations: Sequence[int | None]) -> float:
        pairs = zip(counts, durations, strict=True)
        return sum(n * (minutes if d is None else d) for n, d in pairs)

    return estimate


LEGS = [SQUAT, HINGE, CURL, CALF]  # 13 sets of 5 minutes and the warm-up: 70 minutes


@pytest.mark.parametrize(
    ("minutes", "sets", "dropped", "fits", "length"),
    [
        (None, (4, 3, 3, 3), (), True, 70),  # as planned
        (70, (4, 3, 3, 3), (), True, 70),  # it fits as it is
        (65, (3, 3, 3, 3), (), True, 65),  # 1: fourth sets go
        (64, (2, 2, 2, 2), (), True, 45),  # 2: third sets go
        (44, (2, 2, 0, 2), (2,), True, 35),  # 4: the curl; the hinge trains hamstrings
        (34, (2, 2, 0, 0), (2, 3), True, 25),  # then the calf raise, which nothing else trains
        (24, (2, 2, 0, 0), (2, 3), True, 22),  # 30 or less: ramp sets, 2 minutes
        (20, (2, 0, 0, 0), (2, 3, 1), True, 12),  # main patterns: the later goes first
        (10, (2, 0, 0, 0), (2, 3, 1), False, 12),  # 5: never the last exercise
    ],
)
def test_each_rule_applies_only_while_it_does_not_fit(
    minutes: int | None,
    sets: tuple[int, ...],
    dropped: tuple[int, ...],
    fits: bool,
    length: int,
) -> None:
    trimmed = trim(LEGS, minutes, per_set())
    assert (trimmed.sets, trimmed.dropped, trimmed.fits, trimmed.minutes) == (
        sets,
        dropped,
        fits,
        length,
    )
    assert trimmed.shortest == (None if fits else length)


def test_as_planned_changes_nothing() -> None:
    trimmed = trim([SQUAT, RUN], None, per_set())
    assert trimmed.sets == (4, 1)
    assert trimmed.durations == (None, 30)
    assert trimmed.warm_up is WarmUp.FULL
    assert trimmed.shortest is None


def test_sets_go_from_every_exercise_at_once() -> None:
    """45 minutes of sets and the warm-up; one fewer set of either would do, both lose theirs."""
    trimmed = trim([replace(SQUAT, sets=5), SQUAT], 49, per_set())
    assert trimmed.sets == (3, 3)
    assert trimmed.minutes == 35


def test_an_exercise_planned_with_fewer_sets_keeps_them() -> None:
    trimmed = trim([SQUAT, replace(CALF, sets=1)], 16, per_set(), has_warm_up=False)
    assert trimmed.sets == (2, 1)


@pytest.mark.parametrize(
    ("items", "order"),
    [
        # covered accessory before uncovered accessory, even when it comes earlier
        ([HINGE, CURL, CALF, ROLLOUT], (1, 3, 2)),
        # an accessory without prime movers isn't covered
        ([HINGE, CURL, MOBILITY], (1, 2)),
        # a carry is accessory work: it goes before a main pattern
        ([PUSH, CARRY], (1,)),
        ([CARRY, PUSH], (0,)),
        # a covered main pattern before an uncovered one: the pulldown, the row trains lats
        ([PULLDOWN, ROW, PUSH], (0, 2)),
        # cardio is main work, and covers nothing
        ([RUN, ROLLOUT], (1,)),
    ],
)
def test_whole_exercises_go_by_the_key(items: list[Item], order: tuple[int, ...]) -> None:
    trimmed = trim(items, 1, per_set(), has_warm_up=False)
    assert trimmed.dropped == order
    assert not trimmed.fits


def test_two_covered_accessories_the_later_goes_first() -> None:
    trimmed = trim([HINGE, CURL, replace(CURL, sets=2)], 1, per_set(), has_warm_up=False)
    assert trimmed.dropped == (2, 1)


def test_coverage_counts_only_exercises_still_in_the_session() -> None:
    """Two curls cover each other until one goes; then the other is uncovered, like the calf
    raise, which comes later and so goes first."""
    trimmed = trim([CURL, replace(CURL, sets=2), CALF], 1, per_set(), has_warm_up=False)
    assert trimmed.dropped == (1, 2)


def test_keep_pins_an_exercise() -> None:
    trimmed = trim([HINGE, replace(CURL, keep=True), CALF], 1, per_set(), has_warm_up=False)
    assert trimmed.dropped == (2, 0)
    assert trimmed.sets == (0, 2, 0)


def test_keep_still_loses_sets() -> None:
    trimmed = trim([replace(SQUAT, keep=True), CALF], 21, per_set(), has_warm_up=False)
    assert trimmed.sets == (2, 2)


def test_when_every_exercise_is_kept_nothing_goes() -> None:
    kept = [replace(SQUAT, keep=True), replace(CALF, keep=True)]
    trimmed = trim(kept, 1, per_set(), has_warm_up=False)
    assert trimmed.sets == (2, 2)
    assert trimmed.dropped == ()
    assert trimmed.shortest == 20


@pytest.mark.parametrize(
    ("minutes", "durations", "sets", "fits"),
    [
        (45, (30, None), (1, 3), True),
        (40, (30, None), (1, 2), True),  # 2: the third set goes first
        (35, (25, None), (1, 2), True),  # 3: then the run shortens to what fits
        (20, (10, None), (1, 2), True),
        (15, (10, None), (1, 0), True),  # never under 10 minutes: then exercises go
        (5, (10, None), (1, 0), False),
    ],
)
def test_a_duration_item_shortens_never_below_10_minutes(
    minutes: int, durations: tuple[int | None, ...], sets: tuple[int, ...], fits: bool
) -> None:
    trimmed = trim([RUN, ROLLOUT], minutes, per_set(), has_warm_up=False)
    assert (trimmed.durations, trimmed.sets, trimmed.fits) == (durations, sets, fits)


@pytest.mark.parametrize(
    ("items", "minutes", "durations"),
    [
        # the longest a minute at a time, the later on a tie
        ([replace(RUN, minutes=20), replace(RUN, minutes=20)], 37, (19, 18)),
        # one planned under the floor stays as it is
        ([replace(RUN, minutes=8), RUN], 20, (8, 12)),
        # an item with no sets planned isn't shortened
        ([replace(RUN, sets=0), RUN], 20, (30, 20)),
    ],
)
def test_duration_items_shorten_evenly(
    items: list[Item], minutes: int, durations: tuple[int | None, ...]
) -> None:
    trimmed = trim(items, minutes, per_set(), has_warm_up=False)
    assert trimmed.durations == durations
    assert trimmed.fits


@pytest.mark.parametrize(
    ("minutes", "level", "expected"),
    [
        (None, None, WarmUp.FULL),
        (31, None, WarmUp.FULL),
        (30, None, WarmUp.RAMP),  # no level yet reads as 4 or above
        (30, 4, WarmUp.RAMP),
        (30, 3, WarmUp.FULL),  # a first exercise at level 3 or below keeps the warm-up
        (20, 1, WarmUp.FULL),
    ],
)
def test_ramp_sets_at_30_minutes_or_less(
    minutes: int | None, level: int | None, expected: WarmUp
) -> None:
    assert warm_up([replace(SQUAT, level=level)], [4], minutes) is expected


def test_ramp_sets_follow_the_first_exercise_still_in_the_session() -> None:
    items = [replace(SQUAT, level=2), replace(CALF, level=5)]
    assert warm_up(items, [4, 3], 30) is WarmUp.FULL
    assert warm_up(items, [0, 3], 30) is WarmUp.RAMP
    assert warm_up([], [], 30) is WarmUp.RAMP


def test_ramp_sets_count_as_2_minutes() -> None:
    """28 minutes of work: 33 with the warm-up, 30 with ramp sets."""
    items = [replace(SQUAT, sets=2), replace(HINGE, sets=2), replace(CALF, sets=2)]
    estimate = per_set(28 / 6)
    assert trim(items, 30, estimate).warm_up is WarmUp.RAMP
    assert trim(items, 30, estimate).fits
    assert trim(items, 32, estimate).sets == (2, 2, 0)  # over 30: the full warm-up, so a cut


def test_a_session_without_a_warm_up_counts_none() -> None:
    trimmed = trim([SQUAT], 20, per_set(), has_warm_up=False)
    assert trimmed.warm_up is WarmUp.NONE
    assert trimmed.minutes == 20


def test_it_fits_by_the_estimate_rounded_as_the_overview_shows_it() -> None:
    trimmed = trim([SQUAT], 40, lambda counts, durations: 35.4)
    assert trimmed.fits
    assert trimmed.sets == (4,)
    assert trimmed.minutes == 40
