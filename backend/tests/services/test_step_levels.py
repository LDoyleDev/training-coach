"""A level and marks on every ladder step, and failure_ok per exercise (ADR-0083, ADR-0084)."""

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.services.test_seed import DIP_LEVELS, MINI_PLAN
from training_coach.db.models import Exercise
from training_coach.domain.step_levels import Mark
from training_coach.services.seed import apply_seed, load_plan


def _dip(facts: str, plan: str = MINI_PLAN) -> str:
    return plan.replace(DIP_LEVELS, facts)


@pytest.mark.parametrize(
    ("facts", "error"),
    [
        ('levels = { "Feet down" = 4 }', r"dip: no level for \['Feet up'\]"),
        (DIP_LEVELS.replace("}", ", Rings = 6 }"), r"levels for \['Rings'\]"),
        ('levels = { "Feet down" = 5, "Feet up" = 4 }', "'Feet up' is a lower level than"),
        ('levels = { "Feet down" = 4, "Feet up" = 7 }', "levels.Feet up"),
        ('levels = { "Feet down" = 0, "Feet up" = 4 }', "levels.Feet down"),
        (DIP_LEVELS + '\nmarks = { Rings = ["hanging"] }', r"marks for \['Rings'\]"),
        (DIP_LEVELS + '\nmarks = { "Feet up" = ["wet"] }', "marks.Feet up.0"),
        (DIP_LEVELS + '\nmarks = { "Feet up" = [] }', "marks.Feet up"),
        (DIP_LEVELS + '\nmarks = { "Feet up" = ["floor", "floor"] }', "listed twice"),
    ],
    ids=[
        "missing",
        "unknown-step",
        "falls",
        "above-6",
        "below-1",
        "marks-unknown-step",
        "unknown-mark",
        "no-marks",
        "mark-twice",
    ],
)
def test_levels_and_marks_are_checked(facts: str, error: str) -> None:
    with pytest.raises(ValidationError, match=error):
        load_plan(_dip(facts))


def test_a_retired_exercise_may_leave_steps_without_a_level_but_not_falling() -> None:
    retired = 'retired = true\nladder = ["Feet down", "Feet up"]\n\n[[sessions]]'
    plan = MINI_PLAN.replace('ladder = ["Feet down", "Feet up"]\n\n[[sessions]]', retired)
    plan = plan.replace('items = [{ exercise = "dip"', 'items = [{ exercise = "pull-up"')
    dip = next(e for e in load_plan(_dip("", plan)).exercises if e.slug == "dip")
    assert dip.retired
    assert dip.levels == {}
    with pytest.raises(ValidationError, match="lower level"):
        load_plan(_dip('levels = { "Feet down" = 5, "Feet up" = 4 }', plan))


def test_only_an_exercise_counted_in_reps_has_a_last_set_to_failure() -> None:
    reps = 'kind = "reps"\nmuscles = { chest = 1 }'
    walk = MINI_PLAN.replace(reps, reps.replace("reps", "seconds"))
    load_plan(walk)
    with pytest.raises(ValidationError, match="last set to failure"):
        load_plan(walk.replace(DIP_LEVELS, DIP_LEVELS + "\nfailure_ok = true"))


def test_the_seed_stores_levels_marks_and_failure_ok_and_rewrites_them(session: Session) -> None:
    marked = DIP_LEVELS + '\nfailure_ok = true\nmarks = { "Feet up" = ["floor", "kneeling"] }'
    apply_seed(session, load_plan(_dip(marked)))
    session.commit()
    dip = session.scalars(select(Exercise).where(Exercise.slug == "dip")).one()
    assert dip.failure_ok is True
    assert [(s.level, s.marks) for s in dip.ladder] == [(4, []), (5, ["floor", "kneeling"])]
    assert not apply_seed(session, load_plan(_dip(marked))).changed

    apply_seed(session, load_plan(_dip('levels = { "Feet down" = 3, "Feet up" = 3 }')))
    session.commit()
    session.refresh(dip)
    assert dip.failure_ok is False
    assert [(s.level, s.marks) for s in dip.ladder] == [(3, []), (3, [])]


# --------------------------------------------------------------- the bundled plan


def test_every_bundled_step_has_a_level_and_known_marks() -> None:
    """Retired exercises too: the goblet squat comes back as the Squat entry (ADR-0083)."""
    for exercise in load_plan().exercises:
        assert set(exercise.levels) == set(exercise.ladder), exercise.slug
        assert all(set(marks) <= set(Mark) for marks in exercise.marks.values())


# (slug, step) -> (level, marks): a sample across the scale, so a change is deliberate.
PINNED = {
    ("push-up", "Standard"): (4, {"floor"}),
    ("push-up", "Archer"): (6, {"floor"}),
    ("pull-up", "Slow negatives"): (4, {"hanging"}),
    ("pull-up", "Vest or backpack"): (6, {"hanging"}),
    ("lateral-raise", "8 kg or water bottles"): (2, set()),
    ("tibialis-raise", "Back against wall, heels forward"): (2, set()),
    ("calf-raise", "Bodyweight on a step"): (3, {"balance"}),
    ("kb-curl", "8 kg"): (3, set()),
    ("suitcase-carry", "8 kg"): (3, set()),
    ("chin-tuck", "5 s hold"): (1, set()),
    ("zone2", "Brisk walk / hike"): (2, set()),
    ("zone2", "Easy jog with weight vest or backpack"): (6, {"impact"}),
    ("jump-squat", "Bodyweight, full rest"): (4, {"impact"}),
    ("kb-swing", "Two-hand, 8 kg"): (4, set()),
    ("kb-swing", "Two-hand, 24 kg"): (6, set()),
    ("bulgarian-split-squat", "Bodyweight, back foot on chair"): (4, {"balance"}),
    ("pistol-squat", "Full pistol"): (6, {"balance"}),
    ("hamstring-curl", "Towel slide, both legs"): (4, {"floor"}),
    ("hamstring-curl", "Nordic curl negatives"): (6, {"floor", "kneeling"}),
    ("ab-rollout", "Kneeling towel slide, short range"): (4, {"floor", "kneeling"}),
    ("ab-rollout", "Standing ab wheel negatives"): (6, {"floor"}),
    ("side-plank-hip-dip", "On the knees"): (3, {"floor", "kneeling"}),
    ("dead-hang", "Two hands"): (3, {"hanging"}),
    ("neck-flexion", "Bodyweight, slow"): (3, set()),
    ("back-extension", "Floor superman"): (4, {"floor"}),
    ("hiit", "8 rounds"): (4, set()),
    ("dip", "Dip bars, vest or backpack"): (6, set()),
    ("leg-press", "Machine"): (3, set()),
    ("back-squat", "Barbell"): (4, set()),
    ("glute-bridge", "Standing, at the counter"): (1, set()),
    ("glute-bridge", "On the floor"): (2, {"floor"}),
    ("step-up", "One stair, no hands"): (3, {"balance"}),
    ("plank", "Hands on a counter"): (1, set()),
    ("plank", "On the knees"): (3, {"floor", "kneeling"}),
    ("deadlift", "A bag, from a block"): (2, set()),
    ("deadlift", "24 kg"): (5, set()),
    ("armchair-press-up", "Feet helping"): (1, set()),
    ("band-row", "Light band"): (1, set()),
    ("band-pulldown", "Light band"): (2, set()),
    ("seated-press", "8 kg, one arm at a time"): (3, set()),
    ("balance", "Feet together, holding the counter"): (1, set()),
    ("balance", "One leg, eyes closed"): (5, {"balance"}),
    ("interval-walk", "3 min brisk, 3 min easy"): (2, set()),
}


def test_a_sample_of_bundled_levels_and_marks() -> None:
    exercises = {e.slug: e for e in load_plan().exercises}
    found = {
        (slug, step): (int(exercises[slug].levels[step]), set(exercises[slug].marks.get(step, [])))
        for slug, step in PINNED
    }
    assert found == PINNED


# ADR-0084: isolation and stable exercises; never jumps, swings, pistols, Nordics, loaded
# hinges, carries, neck work, ab rollouts or Copenhagen planks.
FAILURE_OK = {
    "tibialis-raise", "calf-raise", "standing-calf-raise", "seated-calf-raise",
    "kb-curl", "incline-db-curl", "hammer-curl", "lateral-raise", "cable-lateral-raise",
    "leg-extension", "seated-leg-curl", "push-up", "diamond-push-up", "pull-up", "chin-up",
    "band-face-pull", "reverse-fly", "reverse-pec-deck", "prone-ytw", "chest-fly",
    "overhead-cable-extension", "wrist-curl", "lat-pulldown", "chest-supported-row",
    "cable-crunch",
    # the entry exercises (ADR-0083): isolation, seated or held, and a bodyweight bridge
    "glute-bridge", "knee-lift", "adductor-squeeze", "standing-leg-curl", "toe-lift",
    "armchair-press-up", "band-pushdown", "band-row", "band-pull-apart", "band-pulldown",
    "seated-press",
}  # fmt: skip
NEVER = {
    "jump-squat", "kb-swing", "pistol-squat", "hamstring-curl", "single-leg-rdl", "barbell-rdl",
    "back-extension", "back-extension-45", "suitcase-carry", "neck-flexion", "neck-extension",
    "neck-lateral", "chin-tuck", "ab-rollout", "copenhagen-plank", "hiit",
    "deadlift", "hip-hinge", "step-up",  # loaded hinges; a stair is a fall risk
    "interval-walk",
}  # fmt: skip


def test_a_last_set_to_failure_only_where_adr_0084_allows_it() -> None:
    allowed = {e.slug for e in load_plan().exercises if e.failure_ok}
    assert allowed == FAILURE_OK
    assert not allowed & NEVER
