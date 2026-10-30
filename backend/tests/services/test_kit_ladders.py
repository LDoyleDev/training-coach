"""The concrete kit ladders (docs/specs/kit-ladder-proposal.md, accepted 25 Oct 2026): each vague
top step is renamed in place and the rest appended, so nobody's place on a ladder moves."""

from datetime import date

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.services.test_seed import MINI_PLAN
from training_coach.db.models import Exercise, LadderStep, SetLog, Workout
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.services import users
from training_coach.services.seed import ExerciseSeed, PlanSeed, apply_seed, load_plan

KIT_LADDERS = {
    "kb-swing",
    "bulgarian-split-squat",
    "single-leg-rdl",
    "kb-row",
    "overhead-triceps-extension",
    "kb-curl",
    "pull-up",
    "chin-up",
    "dip",
    "band-face-pull",
}


def _before(exercise: ExerciseSeed) -> ExerciseSeed:
    """The exercise as it was before the kit ladders: the renamed step under its old name, and
    nothing after it. The first rename is the kit ladders' (a later one, such as the vest's on
    29 Oct, renames a step it named)."""
    old, new = next(iter(exercise.renames.items()))
    at = exercise.ladder.index(new)
    ladder = [*exercise.ladder[:at], old]
    needs = {step: kit for step, kit in exercise.needs.items() if step in ladder}
    return exercise.model_copy(update={"ladder": ladder, "renames": {}, "needs": needs, "cues": {}})


def _old_plan(plan: PlanSeed) -> PlanSeed:
    return plan.model_copy(
        update={"exercises": [_before(e) if e.renames else e for e in plan.exercises]}
    )


def _exercise(session: Session, slug: str) -> Exercise:
    return session.scalars(select(Exercise).where(Exercise.slug == slug)).one()


def test_only_the_kit_ladders_rename_a_step() -> None:
    assert {e.slug for e in load_plan().exercises if e.renames} == KIT_LADDERS


def test_everyone_stays_on_the_same_step_through_the_renames(session: Session) -> None:
    plan = load_plan()
    apply_seed(session, _old_plan(plan))
    session.flush()
    # The owner stands on every vague top step, with a set logged there, and on the first
    # step of the curl (where Liam is): none of them may move.
    kept: dict[str, int] = {}
    workout = Workout(local_date=date(2026, 10, 24), template_id=None, status=WorkoutStatus.DONE)
    for slug in KIT_LADDERS:
        exercise = _exercise(session, slug)
        top = exercise.ladder[-1]
        state = users.exercise_state(session, exercise.id)
        assert state is not None
        state.ladder_step_id = kept[slug] = top.id
        workout.sets.append(
            SetLog(
                exercise_id=exercise.id, ladder_step_id=top.id, set_no=1, side=Side.BOTH, value=5
            )
        )
    session.add(workout)
    session.commit()

    apply_seed(session, plan)
    session.commit()

    renamed = {e.slug: next(iter(e.renames.values())) for e in plan.exercises if e.renames}
    for slug, step_id in kept.items():
        state = users.exercise_state(session, _exercise(session, slug).id)
        assert state is not None
        assert state.ladder_step_id == step_id, slug
        assert session.get_one(LadderStep, step_id).name == renamed[slug]
    logged = {s.ladder_step_id for s in session.scalars(select(SetLog))}
    assert logged == set(kept.values())
    swing = [s.name for s in _exercise(session, "kb-swing").ladder]
    assert swing == ["Two-hand, 8 kg", "One-arm, 8 kg", "Two-hand, 16 kg", "One-arm, 16 kg",
                     "Two-hand, 24 kg"]  # fmt: skip
    assert not apply_seed(session, plan).changed  # the renames stay harmless once applied


def test_curl_and_triceps_get_an_8_kg_middle_step(session: Session) -> None:
    """Option B (Liam, 25 Oct 2026): the old top becomes a harder 8 kg step, 16 kg after it."""
    plan = {e.slug: e for e in load_plan().exercises}
    for slug, middle in (
        ("kb-curl", "8 kg, 3 s lowering, pause at top"),
        ("overhead-triceps-extension", "8 kg, 1.5 reps"),
    ):
        exercise = plan[slug]
        assert exercise.ladder[2] == middle
        assert exercise.needs[middle] == ["kettlebell:8"]
        assert [exercise.needs[s] for s in exercise.ladder[3:]] == [["kettlebell:16"]] * 2


def test_every_new_step_has_needs_and_a_cue() -> None:
    for exercise in load_plan().exercises:
        if not exercise.renames:
            continue
        new = next(iter(exercise.renames.values()))
        for step in exercise.ladder[exercise.ladder.index(new) :]:
            assert exercise.needs.get(step), (exercise.slug, step)
            assert exercise.cues.get(step), (exercise.slug, step)


def test_the_seed_writes_step_cues(session: Session) -> None:
    apply_seed(session, load_plan())
    session.flush()
    rungs = {s.name: s.cue for s in _exercise(session, "kb-swing").ladder}
    assert rungs["Two-hand, 8 kg"] is None
    assert rungs["Two-hand, 24 kg"] == "Hike it deep between the legs before each rep."


def test_a_cue_must_name_a_step_in_the_ladder() -> None:
    bad = MINI_PLAN.replace(
        'ladder = ["Feet down", "Feet up"]',
        'ladder = ["Feet down", "Feet up"]\n[exercises.cues]\n"Feet sideways" = "Odd."',
    )
    with pytest.raises(ValidationError, match="cues for"):
        load_plan(bad)
