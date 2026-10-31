"""Targets (ADR-0027): a step of about 10% of the range; a miss holds; two misses ease.
Pace (ADR-0057): steady and fast change only the step. A shorter day (ADR-0084): judged on the
sets it planned."""

import pytest

from training_coach.domain.enums import ExerciseKind, Side
from training_coach.domain.progression import combine_sides
from training_coach.domain.targets import Pace, Prescription, step, targets

PULL_UPS = Prescription(sets=4, rep_min=5, rep_max=12)  # step 1
DIPS = Prescription(sets=3, rep_min=8, rep_max=15)  # step 2
TIBIALIS = Prescription(sets=3, rep_min=15, rep_max=25)  # step 3


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        pytest.param(Prescription(3, 4, 8), 1, id="4-8"),
        pytest.param(PULL_UPS, 1, id="5-12"),
        pytest.param(DIPS, 2, id="8-15-half-rounds-up"),
        pytest.param(Prescription(3, 10, 20), 2, id="10-20"),
        pytest.param(TIBIALIS, 3, id="15-25-half-rounds-up"),
        pytest.param(Prescription(1, 1, 1), 1, id="at-least-one"),
        pytest.param(Prescription(3, 20, 30, ExerciseKind.SECONDS), 5, id="seconds-at-least-5"),
        pytest.param(Prescription(3, 20, 60, ExerciseKind.SECONDS), 5, id="seconds-60"),
        pytest.param(Prescription(3, 30, 90, ExerciseKind.SECONDS), 10, id="seconds-90"),
        pytest.param(Prescription(3, 60, 120, ExerciseKind.SECONDS), 10, id="seconds-120"),
        pytest.param(Prescription(1, 30, 40, ExerciseKind.DURATION_MIN), 1, id="minutes"),
    ],
)
def test_step_is_about_ten_percent_of_the_top(item: Prescription, expected: int) -> None:
    assert step(item) == expected


@pytest.mark.parametrize(
    ("item", "history", "expected"),
    [
        pytest.param(PULL_UPS, [], (5, 5, 5, 5), id="no-history-bottom-of-range"),
        pytest.param(PULL_UPS, [[8, 7, 6, 5]], (9, 8, 7, 6), id="spec-example"),
        pytest.param(DIPS, [[10, 9, 8]], (12, 11, 10), id="step-two"),
        pytest.param(TIBIALIS, [[18, 16, 15]], (21, 19, 18), id="step-three"),
        pytest.param(PULL_UPS, [[12, 12, 12, 12]], (12, 12, 12, 12), id="capped-at-top"),
        pytest.param(PULL_UPS, [[11, 12, 15, 9]], (12, 12, 12, 10), id="above-top-clamped"),
        pytest.param(PULL_UPS, [[8, 7]], (9, 8, 8, 8), id="missing-sets-start-from-weakest"),
        pytest.param(PULL_UPS, [[8, 7, 6, 5, 4, 3]], (9, 8, 7, 6), id="extra-sets-ignored"),
        pytest.param(PULL_UPS, [[]], (1, 1, 1, 1), id="empty-first-session-starts-from-zero"),
        # Newest first: the second session aimed 9/8/7/6 and hit only the first two sets.
        pytest.param(
            PULL_UPS, [[9, 8, 6, 5], [8, 7, 6, 5]], (10, 9, 7, 6), id="a-miss-holds-the-target"
        ),
        # Missed set 3 twice at the same target 7: it eases to last value + 1.
        pytest.param(
            PULL_UPS,
            [[10, 9, 5, 7], [9, 8, 6, 6], [8, 7, 6, 5]],
            (11, 10, 6, 8),
            id="two-misses-ease",
        ),
        # A first session below the bottom is the baseline: targets grow from it, no jump.
        pytest.param(PULL_UPS, [[3, 2, 2, 1]], (4, 3, 3, 2), id="below-range-first-is-baseline"),
        pytest.param(
            PULL_UPS, [[3, 3, 2, 1], [3, 2, 2, 1]], (4, 4, 3, 2), id="below-range-miss-holds"
        ),
        pytest.param(
            PULL_UPS,
            [[4, 4, 3, 2], [3, 3, 2, 1], [3, 2, 2, 1]],
            (5, 5, 4, 3),
            id="below-range-hit-grows-by-step",
        ),
    ],
)
def test_targets(item: Prescription, history: list[list[int]], expected: tuple[int, ...]) -> None:
    assert targets(item, history) == expected


def test_fixed_rep_count() -> None:
    swings = Prescription(sets=4, rep_min=20, rep_max=20)
    assert targets(swings, [[20, 18, 20, 15]]) == (20, 20, 20, 17)  # baseline + 2, capped
    assert targets(swings, [[20, 18, 20, 15], [20, 18, 20, 15]]) == (20, 20, 20, 17)  # held
    assert targets(swings, [[20, 18, 20, 15]] * 3) == (20, 19, 20, 16)  # two misses ease


def test_timed_and_duration_steps() -> None:
    plank = Prescription(sets=2, rep_min=20, rep_max=60, kind=ExerciseKind.SECONDS)
    assert targets(plank, [[40, 35]]) == (45, 40)
    zone2 = Prescription(sets=1, rep_min=30, rep_max=40, kind=ExerciseKind.DURATION_MIN)
    assert targets(zone2, [[32]]) == (33,)


SECONDS = ExerciseKind.SECONDS
MINUTES = ExerciseKind.DURATION_MIN


@pytest.mark.parametrize(
    ("item", "steady", "standard", "fast"),
    [
        pytest.param(Prescription(3, 4, 8), 1, 1, 2, id="4-8"),
        pytest.param(PULL_UPS, 1, 1, 2, id="5-12"),
        pytest.param(DIPS, 1, 2, 2, id="8-15"),
        pytest.param(TIBIALIS, 1, 3, 3, id="15-25"),
        pytest.param(Prescription(3, 30, 40), 1, 4, 4, id="30-40"),
        pytest.param(Prescription(3, 20, 60, SECONDS), 5, 5, 10, id="seconds-60"),
        pytest.param(Prescription(3, 30, 90, SECONDS), 5, 10, 10, id="seconds-90"),
        pytest.param(Prescription(3, 60, 180, SECONDS), 5, 20, 20, id="seconds-180"),
        pytest.param(Prescription(1, 30, 40, MINUTES), 1, 1, 2, id="minutes"),
    ],
)
def test_step_per_pace(item: Prescription, steady: int, standard: int, fast: int) -> None:
    assert step(item, Pace.STEADY) == steady
    assert step(item, Pace.STANDARD) == standard == step(item)  # standard is the default
    assert step(item, Pace.FAST) == fast


@pytest.mark.parametrize(
    ("pace", "item", "history", "expected"),
    [
        pytest.param(Pace.STEADY, DIPS, [], (8, 8, 8), id="steady-no-history-bottom"),
        pytest.param(Pace.FAST, DIPS, [], (8, 8, 8), id="fast-no-history-bottom"),
        pytest.param(Pace.STEADY, DIPS, [[10, 9, 8]], (11, 10, 9), id="steady-plus-one"),
        pytest.param(Pace.FAST, PULL_UPS, [[8, 7, 6, 5]], (10, 9, 8, 7), id="fast-plus-two"),
        pytest.param(Pace.FAST, TIBIALIS, [[18, 16, 15]], (21, 19, 18), id="fast-keeps-three"),
        pytest.param(Pace.FAST, PULL_UPS, [[11, 12, 10, 9]], (12, 12, 12, 11), id="fast-capped"),
        pytest.param(
            Pace.STEADY, TIBIALIS, [[24, 25, 25]], (25, 25, 25), id="steady-capped-at-top"
        ),
        # Set 2 missed its held target of 10: held, while the others step from what they did.
        pytest.param(
            Pace.FAST,
            PULL_UPS,
            [[10, 8, 8, 7], [8, 8, 6, 5]],
            (12, 10, 10, 9),
            id="fast-miss-holds",
        ),
        pytest.param(
            Pace.FAST,
            PULL_UPS,
            [[10, 8, 8, 7], [10, 8, 8, 7], [8, 8, 6, 5]],
            (12, 9, 10, 9),
            id="fast-two-misses-ease-by-one",
        ),
        pytest.param(
            Pace.STEADY, PULL_UPS, [[3, 2, 2, 1]], (4, 3, 3, 2), id="steady-below-range-baseline"
        ),
        pytest.param(
            Pace.STEADY,
            Prescription(2, 20, 60, SECONDS),
            [[40, 35]],
            (45, 40),
            id="steady-seconds",
        ),
        pytest.param(
            Pace.FAST, Prescription(2, 20, 60, SECONDS), [[40, 35]], (50, 45), id="fast-seconds"
        ),
        pytest.param(
            Pace.STEADY, Prescription(1, 30, 40, MINUTES), [[32]], (33,), id="steady-minutes"
        ),
        pytest.param(Pace.FAST, Prescription(1, 30, 40, MINUTES), [[32]], (34,), id="fast-minutes"),
    ],
)
def test_targets_per_pace(
    pace: Pace, item: Prescription, history: list[list[int]], expected: tuple[int, ...]
) -> None:
    assert targets(item, history, pace) == expected


@pytest.mark.parametrize(
    "history",
    [
        pytest.param([[8, 7, 6, 5]], id="spec-example"),
        pytest.param([[8, 7]], id="missing-sets-start-from-weakest"),
        pytest.param([[]], id="empty-first-session"),
        pytest.param([[9, 8, 6, 5], [8, 7, 6, 5]], id="a-miss-holds"),
        pytest.param([[10, 9, 5, 7], [9, 8, 6, 6], [8, 7, 6, 5]], id="two-misses-ease"),
    ],
)
def test_sessions_saved_without_a_count_keep_their_targets(history: list[list[int]]) -> None:
    unknown: list[int | None] = [None] * len(history)
    before = targets(PULL_UPS, history)
    assert targets(PULL_UPS, history, planned=unknown) == before
    assert targets(PULL_UPS, history, planned=[4] * len(history)) == before  # as planned


# Newest first, with the sets each session planned. PULL_UPS: 4 sets of 5-12, step 1.
@pytest.mark.parametrize(
    ("item", "history", "planned", "expected"),
    [
        # 10/8/6/5 aimed 11/9/7/6 next; a 2-set day did 11/6. Filling from the weakest would
        # count 6/6 against sets 3 and 4 (12/9/7/7); not planned, they come back from set 2.
        pytest.param(PULL_UPS, [[11, 6], [10, 8, 6, 5]], [2, 4], (12, 9, 9, 9), id="two-set-day"),
        # Then the full day is judged on the targets it was given: 9 for sets 3 and 4.
        pytest.param(
            PULL_UPS,
            [[12, 9, 8, 8], [11, 6], [10, 8, 6, 5]],
            [4, 2, 4],
            (12, 10, 9, 9),
            id="two-set-day-then-full-day",
        ),
        pytest.param(
            PULL_UPS, [[11, 6, 0, 0], [10, 8, 6, 5]], [2, 4], (12, 9, 9, 9), id="logged-past-plan"
        ),
        # Within the planned three, the missing third set starts from the weakest (8).
        pytest.param(
            PULL_UPS, [[10, 8], [9, 8, 7, 6]], [3, 4], (11, 9, 9, 9), id="missing-within-plan"
        ),
        # Sets 3 and 4 had missed once (held 7/6). Back after a 2-set day, they start from set 2
        # with no misses: one more miss holds, it takes a second to ease.
        pytest.param(
            PULL_UPS,
            [[10, 9], [9, 8, 6, 5], [8, 7, 6, 5]],
            [2, 4, 4],
            (11, 10, 10, 10),
            id="returning-sets-start-from-nearest",
        ),
        pytest.param(
            PULL_UPS,
            [[11, 10, 7, 6], [10, 9], [9, 8, 6, 5], [8, 7, 6, 5]],
            [4, 2, 4, 4],
            (12, 11, 10, 10),
            id="returning-set-miss-holds",
        ),
        pytest.param(
            PULL_UPS,
            [[12, 11, 7, 6], [11, 10, 7, 6], [10, 9], [9, 8, 6, 5], [8, 7, 6, 5]],
            [4, 4, 2, 4, 4],
            (12, 12, 8, 7),
            id="returning-set-two-misses-ease",
        ),
        # The exercise dropped for the day: nothing is replayed, every target carries over.
        pytest.param(
            PULL_UPS, [[3, 3, 3, 3], [8, 7, 6, 5]], [0, 4], (9, 8, 7, 6), id="none-planned"
        ),
        pytest.param(PULL_UPS, [[3, 3]], [0], (5, 5, 5, 5), id="none-planned-no-history"),
        # A short first session: sets 3 and 4 show set 2's target, and when first done they
        # are their own baseline, never a miss.
        pytest.param(PULL_UPS, [[8, 7]], [2], (9, 8, 8, 8), id="short-first-session"),
        pytest.param(
            PULL_UPS,
            [[9, 8, 6, 5], [8, 7]],
            [4, 2],
            (10, 9, 7, 6),
            id="a-sets-baseline-is-its-first-planned-session",
        ),
        pytest.param(PULL_UPS, [[8, 7, 6, 5, 4]], [5], (9, 8, 7, 6), id="more-than-prescribed"),
        pytest.param(
            Prescription(2, 20, 60, SECONDS),
            [[45], [40, 35]],
            [1, 2],
            (50, 50),
            id="seconds-one-set-day",
        ),
        # A shortened cardio item counts as dropped, not missed (ADR-0082): no easing.
        pytest.param(
            Prescription(1, 30, 40, MINUTES),
            [[20], [20], [32]],
            [0, 0, 1],
            (33,),
            id="minutes-dropped-not-missed",
        ),
        pytest.param(
            Prescription(1, 30, 40, MINUTES),
            [[20], [20], [32]],
            [None, None, None],
            (21,),
            id="minutes-old-rows-ease",
        ),
    ],
)
def test_targets_on_a_shorter_day(
    item: Prescription,
    history: list[list[int]],
    planned: list[int | None],
    expected: tuple[int, ...],
) -> None:
    assert targets(item, history, planned=planned) == expected


def test_a_shorter_day_at_a_fast_pace() -> None:
    # 10/8/6/5 aimed 12/10/8/7; both planned sets missed and hold, sets 3 and 4 take set 2's.
    assert targets(PULL_UPS, [[11, 6], [10, 8, 6, 5]], Pace.FAST, [2, 4]) == (12, 10, 10, 10)


def test_unilateral_short_day_takes_the_weaker_side_of_its_sets() -> None:
    lunges = Prescription(sets=3, rep_min=8, rep_max=15)  # step 2
    rows = [
        (1, Side.LEFT, 10),
        (1, Side.RIGHT, 9),
        (2, Side.LEFT, 8),
        (2, Side.RIGHT, 9),
        (3, Side.LEFT, 4),  # past the plan, one side: not a 0
    ]
    values = combine_sides(rows, unilateral=True)
    assert values == [9, 8, 0]
    assert targets(lunges, [values], planned=[2]) == (11, 10, 10)
    assert targets(lunges, [values]) == (11, 10, 2)  # saved without a count: a 0


@pytest.mark.parametrize(
    ("history", "planned", "message"),
    [
        pytest.param([[8, 7, 6, 5]], [], "0 planned counts for 1 sessions", id="length"),
        pytest.param([[8, 7, 6, 5]], [-1], "below 0", id="negative"),
    ],
)
def test_invalid_planned_counts(
    history: list[list[int]], planned: list[int | None], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        targets(PULL_UPS, history, planned=planned)


@pytest.mark.parametrize(
    ("sets", "rep_min", "rep_max"),
    [(0, 5, 12), (3, 0, 12), (3, 10, 5)],
    ids=["sets", "min", "range"],
)
def test_invalid_prescription(sets: int, rep_min: int, rep_max: int) -> None:
    with pytest.raises(ValueError, match="invalid prescription"):
        Prescription(sets=sets, rep_min=rep_min, rep_max=rep_max)
