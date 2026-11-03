"""The preferences lock the steps they mark (ADR-0083) the way missing kit does (ADR-0071):
Move up skips them, the levels list says why, a level by hand is allowed with a warning, and a
person already on one stays there."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.bot.messages import feedback_text, progress_text
from training_coach.db.models import Exercise, LadderStep, SessionTemplate, SetLog, Workout
from training_coach.domain.blocks import TOP_STEP_CUE
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.kit import Item
from training_coach.domain.muscles import Kit
from training_coach.domain.progression import Progress
from training_coach.domain.step_levels import Mark
from training_coach.services import (
    ai_summary,
    blocks,
    equipment,
    progress,
    step_locks,
    user_settings,
    users,
)
from training_coach.services.progress import MoveOutcome
from training_coach.services.seed import apply_seed, load_plan

DAY = date(2026, 10, 20)
NOW = datetime(2026, 10, 25, 9, tzinfo=UTC)
TOP = [12, 12, 12, 12]  # pull-up in Torso
KNEELING = "needs kneeling — you've chosen not to kneel"
HANGING = "needs hanging from a bar — you've chosen not to hang"
KNEES = "needs deep knee bending — you've chosen to go easy on your knees"


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


def _ready(
    session: Session,
    step: LadderStep,
    place: str = "home",
    template: str = "torso",
    values: list[int] = TOP,
) -> int:
    """Two sessions at the top of the range at ``step`` (pull-ups in Torso by default);
    returns the second workout."""
    torso = session.scalar(select(SessionTemplate.id).where(SessionTemplate.slug == template))
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
            for n, v in enumerate(values, start=1)
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
    _mark(plan, "pull-up", {4: [Mark.KNEELING]})
    user_settings.update(plan, avoid_kneeling=True)
    strict = _put(plan, "pull-up", 3)
    (item,) = progress.feedback(plan, _ready(plan, strict))
    assert (item.status, item.next_step) == (Progress.READY, "Vest or backpack")
    move = progress.move_up(plan, strict.exercise_id, strict.id)
    assert move is not None
    assert (move.outcome, move.step) == (MoveOutcome.MOVED, "Vest or backpack")


def test_with_every_harder_step_avoided_move_up_says_none_is_open(plan: Session) -> None:
    """Every pull-up step hangs: with "No hanging" nothing above is open, and nothing names the
    preference in ``unlock``, which Telegram and the AI summary say too."""
    user_settings.update(plan, avoid_hanging=True)
    strict = _put(plan, "pull-up", 3)
    (item,) = progress.feedback(plan, _ready(plan, strict))
    assert (item.status, item.unlock) == (Progress.TOP_OF_LADDER, None)
    move = progress.move_up(plan, strict.exercise_id, strict.id)
    assert move is not None
    assert move.outcome is MoveOutcome.NO_NEXT_STEP
    assert _on(plan, strict) == strict.id


def test_what_the_person_avoids_locks_at_the_gym_too(plan: Session) -> None:
    """A gym has every kit (ADR-0071); what the person avoids goes with them."""
    _mark(plan, "pull-up", {4: [Mark.KNEELING]})
    user_settings.update(plan, avoid_kneeling=True)
    strict = _put(plan, "pull-up", 3)
    (item,) = progress.feedback(plan, _ready(plan, strict, place="gym"))
    assert item.next_step == "Vest or backpack"


def test_the_levels_list_says_why_each_step_is_locked_with_kit_too(plan: Session) -> None:
    """Kit and preferences lock together; the kit named to unlock passes a step the person
    avoids, as no kit opens it."""
    _mark(plan, "pull-up", {4: [Mark.KNEELING]})
    user_settings.update(plan, avoid_kneeling=True)
    equipment.save(plan, [Item(Kit.PULL_UP_BAR)], NOW)
    _put(plan, "pull-up", 3)
    pull_up = _standing(plan, "pull-up")
    assert [r.avoided for r in pull_up.ladder] == [(), (), (), (), (KNEELING,), ()]
    assert pull_up.ladder[5].missing == ("a weighted vest or backpack of 5 kg",)
    assert pull_up.unlock == "a weighted vest or backpack of 5 kg unlocks Vest or backpack"


def test_a_step_already_on_stays_and_says_it_is_avoided(plan: Session) -> None:
    """The level never changes by itself: Plan says to pick another step."""
    strict = _put(plan, "pull-up", 3)
    user_settings.update(plan, avoid_hanging=True)
    assert _on(plan, strict) == strict.id
    pull_up = _standing(plan, "pull-up")
    assert pull_up.step_id == strict.id
    assert pull_up.ladder[3].avoided == (HANGING,)


def test_an_avoided_level_can_be_chosen_by_hand_with_a_warning(plan: Session) -> None:
    user_settings.update(plan, avoid_hanging=True)
    first = _put(plan, "pull-up", 2)
    strict = _ladder(plan, "pull-up")[3]
    move = progress.set_level(plan, first.exercise_id, strict.id)
    assert move is not None
    assert move.outcome is MoveOutcome.LEVEL_SET
    assert move.warning == "Strict pull-up " + HANGING + "."
    assert _on(plan, strict) == strict.id


def test_a_strength_block_trains_the_next_open_step(plan: Session) -> None:
    """ADR-0028's one step harder skips locked steps, as Move up does: Pause at top marked
    kneeling, avoided, so a strength block on Strict trains Vest or backpack."""
    _mark(plan, "pull-up", {4: [Mark.KNEELING]})
    user_settings.update(plan, avoid_kneeling=True)
    strict = _put(plan, "pull-up", 3)
    step, at_top = blocks.step_for(plan, strict.exercise, True)
    assert (step.name, at_top) == ("Vest or backpack", False)


def test_a_strength_block_with_no_open_step_above_trains_the_current_one(plan: Session) -> None:
    """Every pull-up step hangs: with "No hanging" the block keeps Strict, with the top's tempo
    cue, never a step the person avoids."""
    user_settings.update(plan, avoid_hanging=True)
    strict = _put(plan, "pull-up", 3)
    assert blocks.step_for(plan, strict.exercise, True) == (strict, True)
    torso = plan.scalars(select(SessionTemplate).where(SessionTemplate.slug == "torso")).one()
    item = next(i for i in torso.items if i.exercise_id == strict.exercise_id)
    assigned = blocks.assign(plan, item, True)
    assert assigned.step == strict
    assert assigned.cue is not None
    assert assigned.cue.endswith(TOP_STEP_CUE)


def test_a_strength_block_skips_kit_locked_steps_at_home_only(plan: Session) -> None:
    """Pause at top is open; with the bar only, Vest or backpack lacks the pack. From Pause at
    top the block stays at home and goes up at the gym, which has everything (ADR-0071)."""
    equipment.save(plan, [Item(Kit.PULL_UP_BAR)], NOW)
    pause = _put(plan, "pull-up", 4)
    assert blocks.step_for(plan, pause.exercise, True) == (pause, True)
    step, at_top = blocks.step_for(plan, pause.exercise, True, at_gym=True)
    assert (step.name, at_top) == ("Vest or backpack", False)


def test_with_every_harder_step_locked_every_surface_says_so_without_why(plan: Session) -> None:
    """The saved feedback, Telegram, the review and the AI summary say "no open step above
    this one" (true, and neutral); "top of the ladder" stays for the real last step."""
    user_settings.update(plan, avoid_hanging=True)
    strict = _put(plan, "pull-up", 3)
    (item,) = progress.feedback(plan, _ready(plan, strict))
    assert (item.status, item.note_top, item.capped) == (Progress.TOP_OF_LADDER, True, True)
    told = feedback_text([item])
    assert "Pull-up: top of the range, with no open step above this one." in told
    for said in ("last level", "top of the ladder", "chosen", "avoid", "hang"):
        assert said not in told.lower(), said
    standing = _standing(plan, "pull-up")
    assert standing.capped
    assert "Pull-up: Strict pull-up (4/6)" in progress_text([standing])
    assert progress_text([standing]).endswith("No open step above this one")
    text = ai_summary.summary(plan, DAY, ai_summary.Options(weeks=4))
    line = next(x for x in text.splitlines() if x.startswith("- Pull-up:"))
    assert line.endswith("; no open step above this one")
    assert "chosen" not in text.lower()


def test_the_real_last_step_is_still_the_top_of_the_ladder(plan: Session) -> None:
    """Hamstring curl's last step, Full Nordic curl, in Legs (3 x 6-15)."""
    last = _put(plan, "hamstring-curl", 3)
    (item,) = progress.feedback(plan, _ready(plan, last, template="legs", values=[15] * 3))
    assert (item.status, item.capped) == (Progress.TOP_OF_LADDER, False)
    assert "last level of its ladder" in feedback_text([item])
    standing = _standing(plan, "hamstring-curl")
    assert not standing.capped
    assert progress_text([standing]).endswith("Top of the ladder")


def test_easy_on_my_knees_locks_the_nordics_from_the_plans_own_marks(plan: Session) -> None:
    """#540: the plan marks both Nordic curls; the towel slides stay open. From the single-leg
    slide nothing above is open, and a Nordic by hand comes with the warning."""
    user_settings.update(plan, avoid_knees=True)
    single = _put(plan, "hamstring-curl", 1)
    assert [r.avoided for r in _standing(plan, "hamstring-curl").ladder] == [
        (),
        (),
        (KNEES,),
        (KNEES,),
    ]
    (item,) = progress.feedback(plan, _ready(plan, single, template="legs", values=[15] * 3))
    assert (item.status, item.capped, item.unlock) == (Progress.TOP_OF_LADDER, True, None)
    move = progress.move_up(plan, single.exercise_id, single.id)
    assert move is not None
    assert move.outcome is MoveOutcome.NO_NEXT_STEP
    nordic = _ladder(plan, "hamstring-curl")[2]
    chosen = progress.set_level(plan, single.exercise_id, nordic.id)
    assert chosen is not None
    assert chosen.warning == "Nordic curl negatives " + KNEES + "."
