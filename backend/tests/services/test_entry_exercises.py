"""The entry exercises for people starting low (ADR-0083): new movements in the catalogue, in
no session yet, each with its own range."""

import pytest
from pydantic import ValidationError

from tests.services.test_seed import DIP_LEVELS, MINI_PLAN
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.muscles import Kit, Muscle, parse_need
from training_coach.domain.step_levels import Mark, StepLevel
from training_coach.services.seed import load_plan

REP_TOP = 18  # ADR-0078
ENTRY_RANGE = (3, 10)  # a level-1 range: a frail person can't miss the bottom on day one

# What this issue adds (#507); the rest of the spec's lower steps extend existing ladders (#508).
ENTRY = {
    "glute-bridge", "step-up", "plank", "knee-lift", "adductor-squeeze", "standing-leg-curl",
    "hip-hinge", "deadlift", "toe-lift",
    "armchair-press-up", "band-pushdown", "band-row", "band-pull-apart", "band-pulldown",
    "seated-press", "balance", "interval-walk",
}  # fmt: skip


def test_a_range_runs_low_to_high_and_only_where_no_session_sets_one() -> None:
    lone = MINI_PLAN.replace("[[sessions]]", '[[exercises]]\nslug = "plank"\nname = "Plank"\n'
        'kind = "seconds"\nmuscles = { abs = 1 }\npattern = "core"\nstart = 0\nladder = ["Wall"]\n'
        'levels = { Wall = 1 }\nRANGE\n\n[[sessions]]', 1)  # fmt: skip
    plank = next(e for e in load_plan(lone.replace("RANGE", "range = [10, 30]")).exercises
                 if e.slug == "plank")  # fmt: skip
    assert plank.range == (10, 30)
    with pytest.raises(ValidationError, match="high to low"):
        load_plan(lone.replace("RANGE", "range = [30, 10]"))
    with pytest.raises(ValidationError, match=r"range.0"):
        load_plan(lone.replace("RANGE", "range = [0, 10]"))
    with pytest.raises(ValidationError, match=r"\['dip'\] have a range, but a session sets"):
        load_plan(MINI_PLAN.replace(DIP_LEVELS, DIP_LEVELS + "\nrange = [5, 10]"))


def test_every_exercise_that_asks_can_you_do_it_has_a_range() -> None:
    """Its questions ask for the bottom of the range: a session's, or its own when no session
    uses it. A one-step gym exercise no session uses asks nothing."""
    plan = load_plan()
    used = {i.exercise for s in plan.sessions for i in (*s.items, *s.gym)}
    unranged = [
        e.slug for e in plan.exercises if e.questions and e.slug not in used and e.range is None
    ]
    assert unranged == []


def test_the_entry_exercises_are_in_the_catalogue_and_in_no_session_yet() -> None:
    """Sessions are shared until builder step 5 (ADR-0073); a starter will use them."""
    plan = load_plan()
    used = {i.exercise for s in plan.sessions for i in (*s.items, *s.gym)}
    entries = {e.slug: e for e in plan.exercises if e.slug in ENTRY}
    assert set(entries) == ENTRY
    assert not ENTRY & used
    assert all(not e.retired and e.summary for e in entries.values())


def test_a_ladder_from_level_1_counted_in_reps_starts_at_3_10() -> None:
    plan = load_plan()
    found = {
        e.slug: e.range
        for e in plan.exercises
        if e.range is not None
        and e.kind is ExerciseKind.REPS
        and e.levels[e.ladder[0]] == StepLevel.SUPPORTED
    }
    assert found
    assert {slug: r for slug, r in found.items() if r != ENTRY_RANGE} == {}
    over = [
        e.slug
        for e in plan.exercises
        if e.range is not None and e.kind is ExerciseKind.REPS and e.range[1] > REP_TOP
    ]
    assert over == []


@pytest.mark.parametrize("strength", ["light", "medium", "heavy"])
def test_a_step_named_for_a_band_needs_that_band(strength: str) -> None:
    """The band entries climb by band strength; a person without that band skips the step
    (ADR-0071)."""
    plan = load_plan()
    named = [
        (e.slug, step)
        for e in plan.exercises
        for step in e.ladder
        if f"{strength} band" in step.lower()
    ]
    assert named
    assert [
        (slug, step)
        for slug, step in named
        if f"band:{strength}" not in next(e for e in plan.exercises if e.slug == slug).needs[step]
    ] == []


# ADR-0083's rule: every muscle on the body map has a step at level 1 or 2 where it is a prime
# mover, done standing or seated, with at most a chair, a wall, a counter, a table, a door frame,
# a band, bottles or a bag. Household things need no kit, so a band is the only kit allowed.
OFF_THE_FLOOR = {Mark.FLOOR, Mark.KNEELING, Mark.HANGING}
# Their way in extends an existing ladder downward, which needs #508's migration: the push-up from
# a wall (chest), the bottle curl (biceps), calf raises holding a wall (calves), the bag held
# beside the counter (forearms, upper traps) and the side lean on a wall (obliques). Take each out
# as #508 lands it; the test fails when one passes, so the list only shrinks.
UNTIL_508 = {
    Muscle.CHEST, Muscle.BICEPS, Muscle.CALVES, Muscle.FOREARMS, Muscle.UPPER_TRAPS,
    Muscle.OBLIQUES,
}  # fmt: skip
# No step planned: the spec's revised list keeps neck work lying down at level 3; the draft's
# seated hand-resistance hold (B2) would pass. Liam's call.
NO_WAY_IN_YET = {Muscle.NECK}


def _ways_in() -> set[Muscle]:
    found = set()
    for e in load_plan().exercises:
        if e.retired:
            continue
        for step in e.ladder:
            kit = {parse_need(need)[0] for need in e.needs.get(step, [])}
            if (
                e.levels[step] <= StepLevel.STARTING
                and not set(e.marks.get(step, [])) & OFF_THE_FLOOR
                and kit <= {Kit.BAND}
            ):
                found |= {m for m, weight in e.muscles.items() if weight == 1}
    return found


def test_every_muscle_has_a_way_in_at_level_1_or_2_standing_or_seated() -> None:
    assert set(Muscle) - _ways_in() == UNTIL_508 | NO_WAY_IN_YET


def test_balance_counts_seconds_and_marks_every_step_without_a_hold() -> None:
    """Move on at 10 s without touching (Otago, SPPB); at levels 1-3 every step is beside a
    counter (ADR-0083)."""
    balance = next(e for e in load_plan().exercises if e.slug == "balance")
    assert balance.kind is ExerciseKind.SECONDS
    assert balance.range == (3, 10)
    assert balance.qualities == ["balance"]
    assert all(Mark.BALANCE in balance.marks[step] for step in balance.ladder[1:])
    low = [step for step in balance.ladder if balance.levels[step] <= StepLevel.BUILDING]
    assert all("counter" in step + balance.cues[step] for step in low)
