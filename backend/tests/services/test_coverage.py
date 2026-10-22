"""The body map for one person, from the bundled plan at their own ladder steps."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, ExerciseState
from training_coach.domain.coverage import Band
from training_coach.domain.muscles import Muscle, Part
from training_coach.services.coverage import plan_coverage, trained_steps
from training_coach.services.seed import apply_seed, load_plan


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def test_the_current_plan_matches_the_research_coverage_table(plan: Session) -> None:
    by = {m.muscle: m for m in plan_coverage(plan).muscles}
    # program-builder-research.md, Coverage: the current plan
    assert {m: (by[m].sets, by[m].days) for m in (Muscle.QUADS, Muscle.GLUTES, Muscle.LATS)} == {
        Muscle.QUADS: (8.5, 1),
        Muscle.GLUTES: (12.5, 1),
        Muscle.LATS: (10, 2),
    }
    assert by[Muscle.GLUTES].band is Band.LIGHT_GREEN  # green by sets, but on one day
    assert by[Muscle.GLUTES].over_session_cap  # 11.5 on Legs
    assert by[Muscle.TRICEPS].missing_parts == (Part.TRICEPS_LONG_HEAD,)
    assert by[Muscle.QUADS].missing_parts == (Part.RECTUS_FEMORIS,)
    assert plan_coverage(plan).main_on_target == 2  # lats and upper back


def test_a_loaded_step_adds_to_the_spine_count(plan: Session) -> None:
    assert plan_coverage(plan).days[0].spine_sets == 6  # swings and single-leg RDLs
    split = plan.scalars(select(Exercise).where(Exercise.slug == "bulgarian-split-squat")).one()
    state = plan.scalars(select(ExerciseState).where(ExerciseState.exercise_id == split.id)).one()
    state.ladder_step_id = split.ladder[1].id  # "Goblet hold, 8 kg"
    plan.flush()
    assert trained_steps(plan)["bulgarian-split-squat"] == "Goblet hold, 8 kg"
    legs = plan_coverage(plan).days[0]
    assert (legs.spine_sets, legs.spine_heavy) == (10, True)


def test_an_exercise_not_started_counts_at_the_plans_start(session: Session) -> None:
    assert trained_steps(session) == {}
    assert plan_coverage(session).days[0].spine_sets == 6
