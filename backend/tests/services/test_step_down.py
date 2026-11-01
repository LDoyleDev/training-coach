"""The step-down suggestion and its answers (ADR-0084), against the bundled plan.

Pull-ups in Torso are 4 sets of 5-12, a step of 1; the plan starts on "Strict pull-up", with
"Slow negatives" below it. Push-ups start on their ladder's first step."""

from datetime import date, timedelta

import pytest
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Event,
    Exercise,
    LadderStep,
    SessionTemplate,
    SetLog,
    Workout,
)
from training_coach.domain.blocks import BlockKind
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.services import progress, users
from training_coach.services.progress import (
    NOT_YET_DOWN,
    Down,
    MoveOutcome,
    feedback,
    not_yet_down,
    overview,
    step_down,
    stepping_down,
)
from training_coach.services.seed import apply_seed, load_plan

DAY = date(2026, 10, 1)
LOW = [2, 2, 2, 2]  # well below the bottom of 5-12


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _exercise(session: Session, slug: str) -> Exercise:
    return session.scalars(select(Exercise).where(Exercise.slug == slug)).one()


def _step(session: Session, slug: str) -> LadderStep:
    state = users.exercise_state(session, _exercise(session, slug).id)
    assert state is not None
    return session.get_one(LadderStep, state.ladder_step_id)


def _log(
    session: Session,
    slug: str,
    values: list[int],
    days: int,
    *,
    block: BlockKind | None = None,
    planned: dict[str, dict[str, int]] | None = None,
) -> int:
    exercise = _exercise(session, slug)
    torso = session.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == "torso"))
    workout = Workout(
        local_date=DAY + timedelta(days=days),
        template_id=torso.one(),
        status=WorkoutStatus.DONE,
        block=block,
        planned=planned,
    )
    step = _step(session, slug)
    workout.sets = [
        SetLog(exercise_id=exercise.id, ladder_step_id=step.id, set_no=n, side=Side.BOTH, value=v)
        for n, v in enumerate(values, start=1)
    ]
    session.add(workout)
    session.flush()
    return workout.id


def _standing(session: Session, slug: str) -> progress.Standing:
    return next(s for s in overview(session) if s.slug == slug)


def _out_of_reach(session: Session, slug: str = "pull-up", values: list[int] = LOW) -> int:
    """A baseline, then two sessions short of their targets and of the range: the last's id."""
    _log(session, slug, values, 0)
    _log(session, slug, values, 2)
    return _log(session, slug, values, 4)


def test_the_bottom_of_the_range_out_of_reach_twice_suggests_the_step_below(
    plan: Session,
) -> None:
    step = _step(plan, "pull-up")
    (item,) = feedback(plan, _out_of_reach(plan))
    assert item.down == Down(step.id, "Slow negatives")
    assert _standing(plan, "pull-up").down == Down(step.id, "Slow negatives")
    assert [r.slug for r in stepping_down(overview(plan))] == ["pull-up"]
    assert _step(plan, "pull-up").id == step.id  # suggested, nothing changed


def test_the_baseline_and_one_more_session_are_not_enough(plan: Session) -> None:
    _log(plan, "pull-up", LOW, 0)
    (item,) = feedback(plan, _log(plan, "pull-up", LOW, 2))
    assert item.down is None
    assert _standing(plan, "pull-up").down is None


def test_growing_below_the_range_is_not_out_of_reach(plan: Session) -> None:
    _log(plan, "pull-up", [2, 2, 2, 2], 0)
    _log(plan, "pull-up", [3, 3, 3, 3], 2)
    (item,) = feedback(plan, _log(plan, "pull-up", [4, 4, 4, 4], 4))
    assert item.down is None


def test_strength_block_sessions_are_passed_over(plan: Session) -> None:
    _log(plan, "pull-up", LOW, 0)
    _log(plan, "pull-up", LOW, 2)
    _log(plan, "pull-up", LOW, 4, block=BlockKind.STRENGTH)
    assert _standing(plan, "pull-up").down is None


def test_a_level_chosen_for_today_is_passed_over(plan: Session) -> None:
    step = _step(plan, "pull-up")
    today = {"pull-up": {"sets": 4, "today": step.id}}
    _log(plan, "pull-up", LOW, 0)
    _log(plan, "pull-up", LOW, 2, planned=today)
    _log(plan, "pull-up", LOW, 4)
    assert _standing(plan, "pull-up").down is None
    _log(plan, "pull-up", LOW, 6)
    assert _standing(plan, "pull-up").down == Down(step.id, "Slow negatives")


def test_only_the_sets_a_day_planned_count(plan: Session) -> None:
    two = {"pull-up": {"sets": 2}}
    _log(plan, "pull-up", LOW, 0)
    _log(plan, "pull-up", [2, 2, 12, 12], 2, planned=two)
    assert feedback(plan, _log(plan, "pull-up", [2, 2, 12, 12], 4, planned=two))[0].down
    _log(plan, "pull-up", [2, 2, 12, 12], 6)  # all four planned: two of four is not most
    assert _standing(plan, "pull-up").down is None


def test_a_loaded_step_lowers_the_weight_instead(plan: Session) -> None:
    pull_up = _exercise(plan, "pull-up")
    loaded = pull_up.ladder[-1]
    assert progress.set_level(plan, pull_up.id, loaded.id) is not None
    _out_of_reach(plan)
    assert _standing(plan, "pull-up").down is None


def test_at_the_first_step_it_names_easier_exercises(plan: Session) -> None:
    push_up = _exercise(plan, "push-up")
    step = push_up.ladder[0]  # the wall push-up since the ladders went down (ADR-0083)
    assert progress.set_level(plan, push_up.id, step.id) is not None
    assert step.position == 0
    _out_of_reach(plan, "push-up")
    found = _standing(plan, "push-up").down
    assert found == Down(step.id, None, progress.easier("push-up"))
    assert step_down(plan, step.exercise_id, step.id) == progress.Move(
        MoveOutcome.NO_STEP_BELOW, "Push-up", step.name
    )


def test_easier_exercises_start_low_and_share_a_prime_mover() -> None:
    found = progress.easier("calf-raise")
    assert "Tibialis raise" not in found  # level 2, but the shins, not the calves
    assert "Band face pull" in progress.easier("reverse-fly")  # rear delts, level 2
    assert progress.easier("gone") == ()


def test_step_down_sets_the_level_as_a_by_hand_change(plan: Session) -> None:
    step = _step(plan, "pull-up")
    _out_of_reach(plan)
    moved = step_down(plan, step.exercise_id, step.id)
    assert moved == progress.Move(MoveOutcome.STEPPED_DOWN, "Pull-up", "Slow negatives")
    assert _step(plan, "pull-up").name == "Slow negatives"
    payloads = plan.scalars(select(Event.payload).where(Event.kind == progress.LEVEL_SET)).all()
    below = _step(plan, "pull-up").id
    assert [(p["from_step_id"], p["to_step_id"]) for p in payloads] == [(step.id, below)]
    # Pressed again, from the same page: it has moved on, nothing changes.
    again = step_down(plan, step.exercise_id, step.id)
    assert again == progress.Move(MoveOutcome.ALREADY_MOVED, "Pull-up")
    assert step_down(plan, step.exercise_id, 999_999) is None


def test_not_yet_dismisses_it_until_a_new_session_meets_the_rule(plan: Session) -> None:
    step = _step(plan, "pull-up")
    _out_of_reach(plan)
    stayed = not_yet_down(plan, step.exercise_id, step.id)
    assert stayed == progress.Move(MoveOutcome.STAYED_DOWN, "Pull-up", step.name)
    assert plan.scalars(select(Event).where(Event.kind == NOT_YET_DOWN)).one()
    assert _standing(plan, "pull-up").down is None
    assert _step(plan, "pull-up").id == step.id
    (item,) = feedback(plan, _log(plan, "pull-up", LOW, 6))
    assert item.down == Down(step.id, "Slow negatives")


def test_not_yet_after_a_move_changes_nothing(plan: Session) -> None:
    step = _step(plan, "pull-up")
    below = _exercise(plan, "pull-up").ladder[0]
    progress.set_level(plan, step.exercise_id, below.id)
    moved = not_yet_down(plan, step.exercise_id, step.id)
    assert moved == progress.Move(MoveOutcome.ALREADY_MOVED, "Pull-up")
    assert not_yet_down(plan, 999_999, step.id) is None
    assert not plan.scalars(select(Event).where(Event.kind == NOT_YET_DOWN)).all()


def test_a_stale_step_down_changes_nothing(plan: Session) -> None:
    """Checked again now, as Move up is: once a Not yet (or a newer session) has removed the
    suggestion, an old page or message can't lower the level."""
    step = _step(plan, "pull-up")
    _out_of_reach(plan)
    assert not_yet_down(plan, step.exercise_id, step.id) is not None
    stale = step_down(plan, step.exercise_id, step.id)
    assert stale == progress.Move(MoveOutcome.NOT_READY, "Pull-up")
    assert _step(plan, "pull-up").id == step.id
    _log(plan, "pull-up", [12, 12, 12, 12], 6)  # a good session: the rule no longer stands
    assert step_down(plan, step.exercise_id, step.id) == stale
    assert not plan.scalars(select(Event).where(Event.kind == progress.LEVEL_SET)).all()


def test_dismissals_are_read_once_per_overview_and_feedback(plan: Session) -> None:
    """The Not yet events are read once for every exercise judged, not once per exercise."""
    pull_up, push_up = _step(plan, "pull-up"), _step(plan, "push-up")
    newest = _out_of_reach(plan)
    _out_of_reach(plan, "push-up")
    not_yet_down(plan, pull_up.exercise_id, pull_up.id)
    assert progress.dismissals(plan) == {(pull_up.exercise_id, pull_up.id, newest)}
    reads: list[str] = []

    def record(*args: object) -> None:
        if progress.NOT_YET_DOWN in str(args[3]):  # the statement's parameters
            reads.append(str(args[2]))

    engine = plan.get_bind()
    sa_event.listen(engine, "before_cursor_execute", record)
    try:
        found = {s.slug: s.down for s in overview(plan)}
        in_overview = len(reads)
        feedback(plan, _log(plan, "push-up", LOW, 6))
    finally:
        sa_event.remove(engine, "before_cursor_execute", record)
    assert found["pull-up"] is None  # dismissed
    assert found["push-up"] == Down(push_up.id, "Hands on a stair or low step")
    assert (in_overview, len(reads)) == (1, 2)  # two exercises judged, one read each call
