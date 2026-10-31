"""The entry exercises for people starting low (ADR-0083): new movements in the catalogue, in
no session yet, each with its own range."""

import pytest
from pydantic import ValidationError

from tests.services.test_seed import DIP_LEVELS, MINI_PLAN
from training_coach.domain.enums import ExerciseKind
from training_coach.domain.step_levels import StepLevel
from training_coach.services.seed import load_plan

REP_TOP = 18  # ADR-0078
ENTRY_RANGE = (3, 10)  # a level-1 range: a frail person can't miss the bottom on day one

# What this issue adds (#507); the rest of the spec's lower steps extend existing ladders (#508).
ENTRY = {
    "glute-bridge", "step-up", "plank", "knee-lift", "adductor-squeeze", "standing-leg-curl",
    "hip-hinge", "deadlift", "toe-lift",
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
