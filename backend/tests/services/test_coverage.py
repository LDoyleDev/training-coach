"""The body map for one person, from the bundled plan at their own ladder steps."""

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, ExerciseState
from training_coach.domain.coverage import Band
from training_coach.domain.enums import Place, Places
from training_coach.domain.muscles import Muscle
from training_coach.services import user_settings
from training_coach.services.coverage import map_place, plan_coverage, trained_steps
from training_coach.services.seed import apply_seed, load_plan


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def test_the_plan_puts_every_main_muscle_on_target(plan: Session) -> None:
    by = {m.muscle: m for m in plan_coverage(plan).muscles}
    # training-plan.md, Weekly hard sets: coverage + core (23 Oct 2026)
    assert {m: (by[m].sets, by[m].days) for m in (Muscle.QUADS, Muscle.GLUTES, Muscle.LATS)} == {
        Muscle.QUADS: (12.5, 3),  # the reverse Nordic on Recovery
        Muscle.GLUTES: (15.5, 2),
        Muscle.LATS: (10, 2),
    }
    assert by[Muscle.GLUTES].band is Band.GREEN  # Legs and Arms
    assert not by[Muscle.GLUTES].over_session_cap  # 10.5 on Legs, under 11
    assert by[Muscle.TRICEPS].missing_parts == ()  # the overhead extension
    assert by[Muscle.QUADS].missing_parts == ()  # the reverse Nordic
    assert plan_coverage(plan).main_on_target == 10


def test_the_core_block_covers_the_trunk_and_hips(plan: Session) -> None:
    by = {m.muscle: m for m in plan_coverage(plan).muscles}
    # program-builder-research.md, Core and hips: Recovery and Cardio + core
    trunk = (Muscle.ABS, Muscle.OBLIQUES, Muscle.LOWER_BACK, Muscle.ADDUCTORS)
    assert {m: (by[m].sets, by[m].days, by[m].band) for m in trunk} == {
        Muscle.ABS: (7, 2, Band.GREEN),
        Muscle.OBLIQUES: (7.75, 2, Band.GREEN),  # + the suitcase carries
        Muscle.LOWER_BACK: (5.5, 2, Band.GREEN),
        Muscle.ADDUCTORS: (6.5, 2, Band.GREEN),
    }
    assert by[Muscle.HIP_FLEXORS].band is Band.GREEN  # 3 on its own 3-8 band
    days = {d.name: d for d in plan_coverage(plan).days}
    assert (days["Cardio + core"].spine_sets, days["Cardio + core"].grip_sets) == (4, 2)
    assert not any(d.spine_heavy or d.grip_heavy for d in days.values())


def test_face_pulls_and_carries_reach_the_rear_delts_and_traps(plan: Session) -> None:
    """Plan version "Rear delts + carries" (25 Oct 2026, training-plan.md)."""
    by = {m.muscle: m for m in plan_coverage(plan).muscles}
    assert (by[Muscle.REAR_DELTS].sets, by[Muscle.REAR_DELTS].days) == (9.25, 2)
    assert by[Muscle.REAR_DELTS].band is Band.GREEN
    assert (by[Muscle.UPPER_TRAPS].sets, by[Muscle.UPPER_TRAPS].days) == (4, 2)
    assert by[Muscle.UPPER_TRAPS].band is Band.LIGHT_GREEN
    assert by[Muscle.FOREARMS].band is Band.GREEN  # one dead-hang set fewer keeps it under 10


def test_a_loaded_step_adds_to_the_spine_count(plan: Session) -> None:
    assert plan_coverage(plan).days[0].spine_sets == 6  # swings and single-leg RDLs
    split = plan.scalars(select(Exercise).where(Exercise.slug == "bulgarian-split-squat")).one()
    state = plan.scalars(select(ExerciseState).where(ExerciseState.exercise_id == split.id)).one()
    state.ladder_step_id = split.ladder[4].id  # "Goblet hold, 8 kg"
    plan.flush()
    assert trained_steps(plan)["bulgarian-split-squat"] == "Goblet hold, 8 kg"
    legs = plan_coverage(plan).days[0]
    assert (legs.spine_sets, legs.spine_heavy) == (9, True)  # + 3 loaded split-squat sets


def test_an_exercise_not_started_counts_at_the_plans_start(session: Session) -> None:
    assert trained_steps(session) == {}
    assert plan_coverage(session).days[0].spine_sets == 6


def test_the_gym_view_counts_each_sessions_gym_version(plan: Session) -> None:
    home, gym = plan_coverage(plan), plan_coverage(plan, Place.GYM)
    assert {d.slug: d.place for d in gym.days} == {
        "legs": Place.GYM,
        "recovery": Place.HOME,  # no gym version: counted the same in both views
        "torso": Place.GYM,
        "moderate-cardio": Place.GYM,
        "hiit": Place.HOME,
        "arms": Place.GYM,
        "zone2": Place.HOME,
    }
    assert {d.place for d in home.days} == {Place.HOME}
    assert gym.days[1] == home.days[1]  # Recovery, the same week in both
    by = {m.muscle: m for m in gym.muscles}
    assert (by[Muscle.HAMSTRINGS].sets, by[Muscle.HAMSTRINGS].days) == (12, 3)
    glutes = {s.exercise for s in by[Muscle.GLUTES].sources}
    assert "Hip thrust" in glutes
    assert "Kettlebell swing" not in glutes  # the home Legs'
    assert gym.days[0].spine_sets == 3  # the gym Legs at its starting steps


@pytest.mark.parametrize(
    ("places", "last", "starts"),
    [
        (Places.HOME, Place.GYM, Place.HOME),
        (Places.GYM, Place.HOME, Place.GYM),
        (Places.BOTH, Place.GYM, Place.GYM),  # the last place chosen on Today's switch
        (Places.BOTH, Place.HOME, Place.HOME),
    ],
)
def test_the_map_starts_at_the_days_place(
    session: Session, places: Places, last: Place, starts: Place
) -> None:
    assert map_place(session) == (Places.HOME, Place.HOME)  # everyone starts at home
    user_settings.update(session, places=places, place=last)
    assert map_place(session) == (places, starts)
