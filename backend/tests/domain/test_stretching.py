from training_coach.domain.stretching import (
    HOLD_SECONDS,
    MAX_ROUNDS,
    ROUNDS,
    SWITCH_SECONDS,
    Step,
    Stretch,
    routine,
    seconds,
)


def stretch(slug: str, *muscles: str, per_side: bool = False) -> Stretch:
    return Stretch(slug, slug.title(), frozenset(muscles), per_side, "cue")


QUAD = stretch("quad", "quads", "hip flexors", per_side=True)
HAM = stretch("ham", "hamstrings", per_side=True)
CALF = stretch("calf", "calves", per_side=True)
CHEST = stretch("chest", "chest")
LATS = stretch("lats", "lats", "upper back")
CATALOGUE = [CHEST, LATS, QUAD, HAM, CALF]
LEGS = {"quads": 10, "hamstrings": 6, "calves": 3}


def test_a_hold_counts_both_sides_and_the_changeover() -> None:
    one_round = HOLD_SECONDS + SWITCH_SECONDS
    assert seconds(CHEST, 2) == 2 * one_round
    assert seconds(QUAD, 2) == 4 * one_round


def test_the_most_worked_muscles_come_first() -> None:
    steps = routine(CATALOGUE, LEGS, 10)
    assert [s.stretch.slug for s in steps][:3] == ["quad", "ham", "calf"]


def test_the_routine_never_runs_over() -> None:
    for minutes in (1, 5, 10, 20, 30):
        assert sum(s.seconds for s in routine(CATALOGUE, LEGS, minutes)) <= minutes * 60


def test_short_time_keeps_to_the_session_muscles() -> None:
    # 10 min: three per-side stretches at two rounds take 480 s; 120 s are left, enough for a
    # third round of the most-worked (80 s) but not of the next, and too little for another.
    steps = routine(CATALOGUE, LEGS, 10)
    assert [(s.stretch.slug, s.rounds) for s in steps] == [
        ("quad", MAX_ROUNDS),
        ("ham", ROUNDS),
        ("calf", ROUNDS),
    ]


def test_more_time_adds_extra_rounds_then_the_rest_of_the_body() -> None:
    steps = routine(CATALOGUE, LEGS, 30)
    assert {s.stretch.slug for s in steps} == {"quad", "ham", "calf", "chest", "lats"}
    rounds = {s.stretch.slug: s.rounds for s in steps}
    assert rounds["quad"] == rounds["ham"] == rounds["calf"] == MAX_ROUNDS
    assert rounds["chest"] == rounds["lats"] == ROUNDS  # not worked today: no extra round


def test_a_muscle_already_covered_does_not_pull_a_second_stretch_forward() -> None:
    quad_again = stretch("quad2", "quads", per_side=True)
    steps = routine([QUAD, quad_again, HAM], {"quads": 10, "hamstrings": 1}, 10)
    assert [s.stretch.slug for s in steps][:2] == ["quad", "ham"]


def test_too_little_time_gives_nothing_and_no_catalogue_gives_nothing() -> None:
    assert routine(CATALOGUE, LEGS, 0) == []
    assert routine([], LEGS, 30) == []


def test_without_worked_muscles_the_catalogue_order_decides() -> None:
    steps = routine([CHEST, LATS], {}, 10)
    assert steps == [Step(LATS, ROUNDS), Step(CHEST, ROUNDS)]  # lats covers two muscles
