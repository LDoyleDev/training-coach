"""The four preferences lock the steps they mark (ADR-0083) the way missing kit does (ADR-0071):
Move up skips them, the levels list says why, a level by hand is allowed with a warning, and a
person already on one stays there."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Exercise, LadderStep, SessionTemplate, SetLog, Workout
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.kit import Item
from training_coach.domain.muscles import Kit
from training_coach.domain.progression import Progress
from training_coach.domain.step_levels import Mark
from training_coach.services import equipment, progress, step_locks, user_settings, users
from training_coach.services.progress import MoveOutcome
from training_coach.services.seed import apply_seed, load_plan

DAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 25, 9, tzinfo=UTC)
TOP = [12, 12, 12, 12]  # pull-up in Torso
KNEELING = "needs kneeling — you've chosen not to kneel"
HANGING = "needs hanging from a bar — you've chosen not to hang"


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _ladder(session: Session, slug: str) -> list[LadderStep]:
    found = session.scalar(select(Exercise).where(Exercise.slug == slug))
    assert found is not None
    return list(found.ladder)


def _put(session: Session, slug: str, position: int) -> LadderStep:
    step = _ladder(session, slug)[position]
    state = users.exercise_state(session, step.exercise_id)
    assert state is not None
    state.ladder_step_id = step.id
    session.flush()
    return step


def _on(session: Session, step: LadderStep) -> int:
    state = users.exercise_state(session, step.exercise_id)
    assert state is not None
    return state.ladder_step_id


def _mark(session: Session, slug: str, marks: dict[int, list[Mark]]) -> None:
    """Give some of an exercise's steps these marks, in place of the plan's."""
    for position, step in enumerate(_ladder(session, slug)):
        if position in marks:
            step.marks = [m.value for m in marks[position]]
    session.flush()


def _ready(session: Session, step: LadderStep, place: str = "home") -> int:
    """Two pull-up sessions at the top of the range at ``step``; returns the second workout."""
    torso = session.scalar(select(SessionTemplate.id).where(SessionTemplate.slug == "torso"))
    workout_id = 0
    for days in (0, 2):
        workout = Workout(
            local_date=DAY + timedelta(days=days),
            template_id=torso,
            status=WorkoutStatus.DONE,
            place=place,
        )
        workout.sets = [
            SetLog(
                exercise_id=step.exercise_id,
                ladder_step_id=step.id,
                set_no=n,
                side=Side.BOTH,
                value=v,
            )
            for n, v in enumerate(TOP, start=1)
        ]
        session.add(workout)
        session.flush()
        workout_id = workout.id
    return workout_id


def _standing(session: Session, slug: str) -> progress.Standing:
    return next(s for s in progress.overview(session) if s.slug == slug)


def test_nothing_avoided_locks_nothing(plan: Session) -> None:
    assert step_locks.limits(plan).avoid == frozenset()
    assert all(not r.avoided for r in _standing(plan, "pull-up").ladder)


def test_move_up_skips_a_step_the_person_avoids(plan: Session) -> None:
    """Pull-up: Slow negatives, Strict, Pause at top, Vest or backpack. With "No kneeling" and
    Pause at top marked kneeling, Move up from Strict lands on Vest or backpack."""
    _mark(plan, "pull-up", {2: [Mark.KNEELING]})
    user_settings.update(plan, avoid_kneeling=True)
    strict = _put(plan, "pull-up", 1)
    (item,) = progress.feedback(plan, _ready(plan, strict))
    assert (item.status, item.next_step) == (Progress.READY, "Vest or backpack")
    move = progress.move_up(plan, strict.exercise_id, strict.id)
    assert move is not None
    assert (move.outcome, move.step) == (MoveOutcome.MOVED, "Vest or backpack")


def test_with_every_harder_step_avoided_move_up_says_none_is_open(plan: Session) -> None:
    """Every pull-up step hangs: with "No hanging" nothing above is open, and nothing names the
    preference in ``unlock``, which Telegram and the AI summary say too."""
    user_settings.update(plan, avoid_hanging=True)
    strict = _put(plan, "pull-up", 1)
    (item,) = progress.feedback(plan, _ready(plan, strict))
    assert (item.status, item.unlock) == (Progress.TOP_OF_LADDER, None)
    move = progress.move_up(plan, strict.exercise_id, strict.id)
    assert move is not None
    assert move.outcome is MoveOutcome.NO_NEXT_STEP
    assert _on(plan, strict) == strict.id


def test_what_the_person_avoids_locks_at_the_gym_too(plan: Session) -> None:
    """A gym has every kit (ADR-0071); what the person avoids goes with them."""
    _mark(plan, "pull-up", {2: [Mark.KNEELING]})
    user_settings.update(plan, avoid_kneeling=True)
    strict = _put(plan, "pull-up", 1)
    (item,) = progress.feedback(plan, _ready(plan, strict, place="gym"))
    assert item.next_step == "Vest or backpack"


def test_the_levels_list_says_why_each_step_is_locked_with_kit_too(plan: Session) -> None:
    """Kit and preferences lock together; the kit named to unlock passes a step the person
    avoids, as no kit opens it."""
    _mark(plan, "pull-up", {2: [Mark.KNEELING]})
    user_settings.update(plan, avoid_kneeling=True)
    equipment.save(plan, [Item(Kit.PULL_UP_BAR)], NOW)
    _put(plan, "pull-up", 1)
    pull_up = _standing(plan, "pull-up")
    assert [r.avoided for r in pull_up.ladder] == [(), (), (KNEELING,), ()]
    assert pull_up.ladder[3].missing == ("a weighted vest or backpack of 5 kg",)
    assert pull_up.unlock == "a weighted vest or backpack of 5 kg unlocks Vest or backpack"


def test_a_step_already_on_stays_and_says_it_is_avoided(plan: Session) -> None:
    """The level never changes by itself: Plan says to pick another step."""
    strict = _put(plan, "pull-up", 1)
    user_settings.update(plan, avoid_hanging=True)
    assert _on(plan, strict) == strict.id
    pull_up = _standing(plan, "pull-up")
    assert pull_up.step_id == strict.id
    assert pull_up.ladder[1].avoided == (HANGING,)


def test_an_avoided_level_can_be_chosen_by_hand_with_a_warning(plan: Session) -> None:
    user_settings.update(plan, avoid_hanging=True)
    first = _put(plan, "pull-up", 0)
    strict = _ladder(plan, "pull-up")[1]
    move = progress.set_level(plan, first.exercise_id, strict.id)
    assert move is not None
    assert move.outcome is MoveOutcome.LEVEL_SET
    assert move.warning == "Strict pull-up " + HANGING + "."
    assert _on(plan, strict) == strict.id
