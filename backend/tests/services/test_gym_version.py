"""A person's gym version of their starter, from where they are placed (S1, Decided 5)."""

from datetime import date

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.services.test_starters import _owners
from training_coach.db.models import (
    Exercise,
    ExerciseState,
    LadderStep,
    PlanVersion,
    SessionTemplate,
    User,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.coverage import Band
from training_coach.domain.enums import Place
from training_coach.domain.muscles import Muscle
from training_coach.services import gym_version, plan_edit
from training_coach.services.coverage import plan_coverage
from training_coach.services.plan_edit import Saved
from training_coach.services.seed import PlanSeed, apply_seed, bundled_plan
from training_coach.services.users import OWNER

DAY = date(2026, 11, 9)
MEMBER = 2


def _member(engine: Engine) -> None:
    """Someone on the 3-day starter, every exercise at its bottom step."""
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=MEMBER))
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, bundled_plan())


def _place(session: Session, steps: dict[str, str]) -> None:
    for slug, name in steps.items():
        state = session.scalars(
            select(ExerciseState).join(Exercise).where(Exercise.slug == slug)
        ).one()
        state.ladder_step_id = session.scalars(
            select(LadderStep.id).where(
                LadderStep.exercise_id == state.exercise_id, LadderStep.name == name
            )
        ).one()


def _gym(session: Session) -> dict[str, list[tuple[str, int, int, int, int | None]]]:
    templates = session.scalars(select(SessionTemplate).order_by(SessionTemplate.position))
    return {
        t.slug: [(i.exercise.slug, i.sets, i.rep_min, i.rep_max, i.pair) for i in t.gym_items]
        for t in templates
    }


def test_at_the_bottom_nothing_is_swapped(engine: Engine) -> None:
    _member(engine)
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as mine:
        assert gym_version.write(mine, bundled_plan(), DAY) == Saved(plan_edit.revision(mine), None)
        assert _gym(mine) == {"three-days-a": [], "three-days-b": [], "three-days-c": []}


def test_each_exercise_placed_high_enough_is_done_as_its_gym_exercise(engine: Engine) -> None:
    _member(engine)
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as mine:
        _place(
            mine,
            {
                "goblet-squat": "To a chair, touch and go",  # the leg press's step
                "doorway-row": "Feet at the frame, 3 s lowering",  # above the row's
                "calf-raise": "Bodyweight on a step",
                "push-up": "Hands on a stair or low step",  # one below the bench press's
            },
        )
        saved = gym_version.write(mine, bundled_plan(), DAY)
        assert isinstance(saved, Saved)
        assert saved.version == gym_version.NOTE
        found = _gym(mine)
        assert mine.scalars(select(PlanVersion.name).where(PlanVersion.since == DAY)).all() == [
            gym_version.NOTE
        ]
    assert found["three-days-a"] == [
        ("leg-press", 3, 10, 15, 1),
        ("chest-supported-row", 3, 8, 12, 1),
        ("push-up", 4, 10, 18, 2),
        ("hip-hinge", 3, 3, 10, 2),
        ("standing-calf-raise", 3, 10, 15, 3),
        ("plank", 2, 10, 30, 3),
        ("lateral-raise", 3, 12, 18, 4),
        ("kb-curl", 2, 12, 18, 4),
        ("balance", 2, 3, 10, None),
    ]
    # 3-day B has the lat pulldown and the seated calf raise
    assert [e for e, *_ in found["three-days-b"]] == [
        "bulgarian-split-squat",
        "push-up",
        "glute-bridge",
        "lat-pulldown",
        "lateral-raise",
        "side-plank-hip-dip",
        "seated-calf-raise",
        "balance",
    ]


def test_writing_it_again_changes_nothing(engine: Engine) -> None:
    _member(engine)
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as mine:
        _place(mine, {"hip-hinge": "Single leg, a hand on the counter"})
        first = gym_version.write(mine, bundled_plan(), DAY)
        again = gym_version.write(mine, bundled_plan(), DAY)
        assert isinstance(first, Saved)
        assert again == Saved(first.revision, None)
        assert ("barbell-rdl", 3, 6, 10, 2) in _gym(mine)["three-days-a"]


@pytest.mark.parametrize(
    ("starter", "back_extension"),
    [
        ("two-days", "two-days-b"),
        ("three-days", "three-days-b"),
        ("four-days", "four-days-lower-2"),
    ],
)
def test_with_every_swap_made_the_lower_back_keeps_4_sets_at_the_gym(
    engine: Engine, starter: str, back_extension: str
) -> None:
    """S1, Decided 10: the Romanian deadlift counts the lower back half, so the 45° back
    extension takes the glute bridge's place once a week; the minutes stay the home ones."""
    plan = PlanSeed.model_validate({**bundled_plan().model_dump(), "new_people": starter})
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=MEMBER))
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, plan)
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as mine:
        _place(mine, {e.slug: e.ladder[-1] for e in plan.exercises})  # every one at its top
        assert isinstance(gym_version.write(mine, plan, DAY), Saved)
        home, gym = plan_coverage(mine), plan_coverage(mine, Place.GYM)
        found = _gym(mine)
    lower = [
        next((m.sets, m.band) for m in c.muscles if m.muscle is Muscle.LOWER_BACK)
        for c in (home, gym)
    ]
    assert lower == [(5, Band.GREEN), (4, Band.GREEN)]  # 2.5, amber, with the deadlift alone
    with_it = [s for s, items in found.items() if "back-extension-45" in {i[0] for i in items}]
    assert with_it == [back_extension]
    assert [d.minutes for d in gym.days] == [d.minutes for d in home.days]


def test_the_owners_cycle_is_never_touched(engine: Engine) -> None:
    """The owner is on no starter, so even at his top steps nothing of his changes."""
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, bundled_plan())
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        _place(mine, {"goblet-squat": "Heavier kettlebell", "calf-raise": "Bodyweight on a step"})
    before = _owners(engine)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert gym_version.edits(mine, bundled_plan()) == []
        assert isinstance(gym_version.write(mine, bundled_plan(), DAY), Saved)
    assert _owners(engine) == before
