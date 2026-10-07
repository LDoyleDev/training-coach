"""What a strength block prescribes, and how its history stays apart (ADR-0028, #26)."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, LadderStep, SessionTemplate, SetLog, Workout
from training_coach.domain.blocks import TOP_STEP_CUE, Block, BlockKind
from training_coach.domain.progression import Progress
from training_coach.domain.queue import local_date
from training_coach.services import progress, user_settings, users, workout_log
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.today import session_plan

BERLIN = ZoneInfo("Europe/Berlin")
STRENGTH = Block(1, BlockKind.STRENGTH, 1)
HYPERTROPHY = Block(2, BlockKind.HYPERTROPHY, 1)


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _template(session: Session, slug: str) -> int:
    return session.scalars(select(SessionTemplate.id).where(SessionTemplate.slug == slug)).one()


def _item(session: Session, template: str, exercise: str):  # type: ignore[no-untyped-def]
    found = session_plan(session, _template(session, template), STRENGTH)
    assert found is not None
    name = session.scalars(select(Exercise.name).where(Exercise.slug == exercise)).one()
    return next(i for i in found.items if i.exercise == name)


def test_a_strength_session_trains_one_step_harder_at_four_to_eight(plan: Session) -> None:
    tibialis = _item(plan, "legs", "tibialis-raise")  # planned 3 x 15-25 at the first step
    assert tibialis.step == "Heels further from wall"
    assert tibialis.targets == (4, 4, 4)  # no strength history: the bottom of 4-8


def test_sets_are_raised_to_three_and_capped_at_four(plan: Session) -> None:
    split = _item(plan, "legs", "bulgarian-split-squat")  # planned 4 sets
    assert len(split.targets) == 4
    neck = _item(plan, "torso", "neck-flexion")  # planned 2 sets
    assert len(neck.targets) == 3


def test_timed_work_and_other_sessions_are_unchanged(plan: Session) -> None:
    hang = _item(plan, "arms", "dead-hang")
    hang_off = session_plan(plan, _template(plan, "arms"))
    assert hang_off is not None
    assert hang == next(i for i in hang_off.items if i.exercise == hang.exercise)
    recovery = session_plan(plan, _template(plan, "recovery"), STRENGTH)
    recovery_off = session_plan(plan, _template(plan, "recovery"))
    assert recovery == recovery_off
    legs_in_hypertrophy = session_plan(plan, _template(plan, "legs"), HYPERTROPHY)
    assert legs_in_hypertrophy == session_plan(plan, _template(plan, "legs"))


def test_the_top_of_the_ladder_adds_a_tempo_cue(plan: Session) -> None:
    exercise = plan.scalars(select(Exercise).where(Exercise.slug == "tibialis-raise")).one()
    state = users.exercise_state(plan, exercise.id)
    assert state is not None
    top = max(exercise.ladder, key=lambda s: s.position)
    state.ladder_step_id = top.id
    tibialis = _item(plan, "legs", "tibialis-raise")
    assert tibialis.step == top.name
    assert tibialis.cue is not None
    assert tibialis.cue.endswith(TOP_STEP_CUE)


def _start_strength_block(session: Session) -> date:
    on = local_date(datetime.now(UTC), BERLIN)
    user_settings.update(session, blocks=True, today=on)
    return on


def test_a_strength_session_is_saved_at_the_harder_step(plan: Session) -> None:
    on = _start_strength_block(plan)  # the queue starts at Legs, a strength session
    saved = workout_log.save(plan, workout_log.draft(plan, "tibialis 8 7 6", on, BERLIN), BERLIN)
    assert isinstance(saved, workout_log.Saved)
    step = plan.scalars(
        select(LadderStep.name).join(SetLog, SetLog.ladder_step_id == LadderStep.id)
    ).first()
    assert step == "Heels further from wall"
    workout = plan.get(Workout, saved.workout_id)
    assert workout is not None
    assert workout.block == BlockKind.STRENGTH


def test_strength_sets_never_become_hypertrophy_targets(plan: Session) -> None:
    on = _start_strength_block(plan)
    workout_log.save(plan, workout_log.draft(plan, "tibialis 8 8 8", on, BERLIN), BERLIN)
    # Later, moved up to that step in a hypertrophy block: its targets start fresh.
    exercise = plan.scalars(select(Exercise).where(Exercise.slug == "tibialis-raise")).one()
    state = users.exercise_state(plan, exercise.id)
    assert state is not None
    harder = next(s for s in exercise.ladder if s.name == "Heels further from wall")
    state.ladder_step_id = harder.id
    later = session_plan(plan, _template(plan, "legs"), HYPERTROPHY)
    assert later is not None
    tibialis = next(i for i in later.items if i.exercise == exercise.name)
    assert tibialis.targets == (15, 15, 15)  # the bottom of 15-25, not 8 + 3


def test_no_move_up_during_a_strength_block(plan: Session) -> None:
    """The same ready workout offers Move up with blocks off, and not in a strength block."""
    on = local_date(datetime.now(UTC), BERLIN)
    saved = None
    for days_ago in (4, 2):  # two sessions at the top: ready to move up
        draft = workout_log.draft(
            plan, "pull-ups 12 12 12 12", on - timedelta(days=days_ago), BERLIN
        )
        saved = workout_log.save(plan, draft, BERLIN)
    assert isinstance(saved, workout_log.Saved)

    def pull_up_status() -> Progress:
        found = progress.feedback(plan, saved.workout_id, BERLIN)
        return next(f.status for f in found if f.exercise == "Pull-up")

    assert pull_up_status() is Progress.READY
    user_settings.update(plan, blocks=True, today=on - timedelta(days=5))  # a strength block
    assert pull_up_status() is Progress.HOLD

    exercise = plan.scalars(select(Exercise).where(Exercise.slug == "pull-up")).one()
    state = users.exercise_state(plan, exercise.id)
    assert state is not None
    move = progress.move_up(plan, exercise.id, state.ladder_step_id, strength_block=True)
    assert move is not None
    assert move.outcome is progress.MoveOutcome.STRENGTH_BLOCK


def test_turning_blocks_on_after_drafting_makes_the_draft_stale(plan: Session) -> None:
    """Trained the ordinary prescription, then turned blocks on: saving it as strength would
    file the sets one step too high. It is refused; the log is sent again."""
    on = local_date(datetime.now(UTC), BERLIN)
    drafted = workout_log.draft(plan, "tibialis 20 18 16", on, BERLIN)
    user_settings.update(plan, blocks=True, today=on)
    assert isinstance(workout_log.save(plan, drafted, BERLIN), workout_log.Stale)
    assert plan.scalars(select(Workout.id)).all() == []


def test_turning_blocks_off_after_drafting_makes_the_draft_stale(plan: Session) -> None:
    on = _start_strength_block(plan)
    drafted = workout_log.draft(plan, "tibialis 8 7 6", on, BERLIN)
    assert drafted.strength
    user_settings.update(plan, blocks=False)
    assert isinstance(workout_log.save(plan, drafted, BERLIN), workout_log.Stale)


def test_no_move_up_offered_when_today_starts_a_strength_block(plan: Session) -> None:
    """Logged on the last hypertrophy days, saved once a strength block began: no button the
    bot would then refuse."""
    on = local_date(datetime.now(UTC), BERLIN)
    saved = None
    for days_ago in (4, 2):
        draft = workout_log.draft(
            plan, "pull-ups 12 12 12 12", on - timedelta(days=days_ago), BERLIN
        )
        saved = workout_log.save(plan, draft, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    # Blocks started 56 days ago: today begins block 3 (strength); 2 days ago was hypertrophy.
    user_settings.update(plan, blocks=True, today=on - timedelta(days=56))
    found = progress.feedback(plan, saved.workout_id, BERLIN)
    assert next(f.status for f in found if f.exercise == "Pull-up") is Progress.HOLD
