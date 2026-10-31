"""The home kit and the steps it locks (ADR-0071): saving the list, what an item unlocks, and
Move up, the levels list and a level by hand respecting the kit."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Equipment,
    Event,
    Exercise,
    LadderStep,
    SessionTemplate,
    SetLog,
    Workout,
)
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.kit import Item, Resistance
from training_coach.domain.muscles import Kit
from training_coach.domain.progression import Progress
from training_coach.services import equipment, home, progress, review, users
from training_coach.services.progress import MoveOutcome
from training_coach.services.seed import apply_seed, load_plan

NOW = datetime(2026, 10, 25, 9, tzinfo=UTC)
DAY = date(2026, 10, 20)
KB8 = Item(Kit.KETTLEBELL, kg=8)
KB16 = Item(Kit.KETTLEBELL, kg=16)
TOP = [20, 20, 20]  # kb-swing in Legs: 3 x 15-20


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _exercise(session: Session, slug: str) -> Exercise:
    found = session.scalar(select(Exercise).where(Exercise.slug == slug))
    assert found is not None
    return found


def _put(session: Session, slug: str, position: int) -> LadderStep:
    exercise = _exercise(session, slug)
    state = users.exercise_state(session, exercise.id)
    assert state is not None
    state.ladder_step_id = exercise.ladder[position].id
    session.flush()
    return exercise.ladder[position]


def _on(session: Session, exercise_id: int) -> int:
    state = users.exercise_state(session, exercise_id)
    assert state is not None
    return state.ladder_step_id


def _standing(session: Session, slug: str) -> progress.Standing:
    return next(s for s in progress.overview(session) if s.slug == slug)


def _ready(
    session: Session,
    step: LadderStep,
    template: str = "legs",
    values: list[int] = TOP,
    sides: tuple[Side, ...] = (Side.BOTH,),
) -> int:
    """Two sessions at the top of the range at ``step``; returns the second workout."""
    template_id = session.scalar(select(SessionTemplate.id).where(SessionTemplate.slug == template))
    workout_id = 0
    for days in (0, 2):
        workout = Workout(
            local_date=DAY + timedelta(days=days),
            template_id=template_id,
            status=WorkoutStatus.DONE,
        )
        workout.sets = [
            SetLog(
                exercise_id=step.exercise_id,
                ladder_step_id=step.id,
                set_no=n,
                side=side,
                value=v,
            )
            for n, v in enumerate(values, start=1)
            for side in sides
        ]
        session.add(workout)
        session.flush()
        workout_id = workout.id
    return workout_id


def test_no_kit_is_listed_until_one_is_saved(plan: Session) -> None:
    assert equipment.kit(plan) is None
    assert equipment.save(plan, [], NOW) is None
    assert equipment.kit(plan) == []  # bodyweight only: a kit too
    assert equipment.saved_at(plan) == NOW


def test_saving_replaces_the_whole_list(plan: Session) -> None:
    stools = Item(Kit.BENCH, note="two stools")
    assert equipment.save(plan, [KB8, Item(Kit.BAND, resistance=Resistance.LIGHT)], NOW) is None
    assert equipment.save(plan, [KB8, KB16, stools], NOW) is None
    plan.flush()
    assert equipment.items(plan) == [KB8, KB16, stools]
    assert len(plan.scalars(select(Equipment)).all()) == 3
    kinds = plan.scalars(select(Event.payload).where(Event.kind == equipment.SAVED)).all()
    assert kinds == [{"items": 2}, {"items": 3}]


def test_a_bad_list_changes_nothing(plan: Session) -> None:
    equipment.save(plan, [KB8], NOW)
    assert equipment.save(plan, [KB16, KB16], NOW) == "16 kg kettlebell is listed twice"
    assert equipment.items(plan) == [KB8]


def test_what_a_16_kg_kettlebell_unlocks(plan: Session) -> None:
    equipment.save(plan, [KB8, Item(Kit.PULL_UP_BAR)], NOW)
    found = {(u.slug, u.step) for u in equipment.unlocks(plan, KB16)}
    assert ("kb-swing", "Two-hand, 16 kg") in found
    assert ("suitcase-carry", "Farmer carry, 16 kg + 8 kg, swap hands each set") in found
    assert ("goblet-squat", "Heavier kettlebell") in found  # the Squat, back (ADR-0083)
    assert all(step != "Two-hand, 8 kg" for _, step in found)  # already open


def test_move_up_and_the_levels_list_ignore_kit_until_it_is_listed(plan: Session) -> None:
    step = _put(plan, "kb-swing", 1)
    last = _ready(plan, step)
    (item,) = progress.feedback(plan, last)
    assert (item.status, item.next_step, item.unlock) == (
        Progress.READY,
        "Two-hand, 16 kg",
        None,
    )
    swing = _standing(plan, "kb-swing")
    assert all(not r.missing for r in swing.ladder)


def test_at_the_top_for_the_kit_progress_names_what_unlocks_the_next_step(plan: Session) -> None:
    equipment.save(plan, [KB8], NOW)
    step = _put(plan, "kb-swing", 1)
    last = _ready(plan, step)
    (item,) = progress.feedback(plan, last)
    assert item.status is Progress.TOP_OF_LADDER
    assert item.unlock == "a 16 kg kettlebell unlocks Two-hand, 16 kg"
    assert item.note_top
    swing = _standing(plan, "kb-swing")
    assert swing.status is Progress.TOP_OF_LADDER
    assert swing.unlock == "a 16 kg kettlebell unlocks Two-hand, 16 kg"
    lacks_16 = ("a 16 kg kettlebell",)
    assert [r.missing for r in swing.ladder] == [
        (),
        (),
        lacks_16,
        lacks_16,
        ("a 24 kg kettlebell",),
    ]
    move = progress.move_up(plan, step.exercise_id, step.id)
    assert move is not None
    assert move.outcome is MoveOutcome.NO_NEXT_STEP
    assert _on(plan, step.exercise_id) == step.id


def test_at_the_gym_the_home_kit_locks_nothing(plan: Session) -> None:
    """Kit locks apply at home only (ADR-0071): a gym has the 16 kg bell."""
    equipment.save(plan, [KB8], NOW)
    step = _put(plan, "kb-swing", 1)
    last = _ready(plan, step)
    plan.get_one(Workout, last).place = "gym"
    plan.flush()
    (item,) = progress.feedback(plan, last)
    assert (item.status, item.next_step, item.unlock) == (Progress.READY, "Two-hand, 16 kg", None)


def test_adding_the_kettlebell_opens_the_next_step(plan: Session) -> None:
    equipment.save(plan, [KB8, KB16], NOW)
    step = _put(plan, "kb-swing", 1)
    _ready(plan, step)
    move = progress.move_up(plan, step.exercise_id, step.id)
    assert move is not None
    assert (move.outcome, move.step) == (MoveOutcome.MOVED, "Two-hand, 16 kg")


def test_move_up_goes_to_the_next_step_the_kit_allows(plan: Session) -> None:
    """Suitcase carry: bags, 8 kg, 16 kg, then 16 + 8 kg. With only the 16 kg bell, both 8 kg
    steps are locked: from the first, Move up goes to 16 kg, which is then the top for the kit."""
    equipment.save(plan, [KB16], NOW)
    carry = _standing(plan, "suitcase-carry")
    lacks_8 = ("an 8 kg kettlebell",)
    assert [r.missing for r in carry.ladder] == [(), (), (), lacks_8, (), lacks_8]
    assert carry.unlock is None  # a harder step is open
    first = _put(plan, "suitcase-carry", 3)  # 8 kg, above the bags
    _ready(plan, first, "recovery", [45, 45], (Side.LEFT, Side.RIGHT))
    move = progress.move_up(plan, first.exercise_id, first.id)
    assert move is not None
    assert (move.outcome, move.step) == (MoveOutcome.MOVED, "16 kg")
    assert _standing(plan, "suitcase-carry").unlock == (
        "an 8 kg kettlebell unlocks Farmer carry, 16 kg + 8 kg, swap hands each set"
    )


def _needs(monkeypatch: pytest.MonkeyPatch, slug: str, needs: dict[str, list[str]]) -> None:
    """Give one exercise's steps these needs, through the service the progress code reads."""
    real = equipment.step_needs
    monkeypatch.setattr(equipment, "step_needs", lambda s: needs if s == slug else real(s))


def test_move_up_skips_a_locked_step_to_the_next_open_one(
    plan: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review of #358: with a saved kit, Move up lands on the next open step, past a locked
    one, and answers no_next_step once the kit blocks the rest."""
    bar = ["pull-up bar"]
    _needs(
        monkeypatch,
        "pull-up",
        {"Slow negatives": bar, "Strict pull-up": bar, "Pause at top": ["rings"]}
        | {"Vest or backpack": bar},
    )
    equipment.save(plan, [Item(Kit.PULL_UP_BAR)], NOW)
    strict = _put(plan, "pull-up", 3)
    _ready(plan, strict, "torso", [12, 12, 12, 12])
    move = progress.move_up(plan, strict.exercise_id, strict.id)
    assert move is not None
    assert (move.outcome, move.step) == (MoveOutcome.MOVED, "Vest or backpack")

    _needs(
        monkeypatch, "pull-up", {name: ["rings"] for name in ("Pause at top", "Vest or backpack")}
    )
    _put(plan, "pull-up", 3)
    blocked = progress.move_up(plan, strict.exercise_id, strict.id)
    assert blocked is not None
    assert blocked.outcome is MoveOutcome.NO_NEXT_STEP
    assert _on(plan, strict.exercise_id) == strict.id


def test_with_no_kit_listed_nothing_locks_through_the_service(plan: Session) -> None:
    """Review of #358: no kit saved, so Move up, a level by hand and feedback behave as
    before: no skipping, no warning, no unlock."""
    step = _put(plan, "kb-swing", 1)
    last = _ready(plan, step)
    (item,) = progress.feedback(plan, last)
    assert item.unlock is None
    move = progress.move_up(plan, step.exercise_id, step.id)
    assert move is not None
    assert (move.outcome, move.step, move.warning) == (
        MoveOutcome.MOVED,
        "Two-hand, 16 kg",
        None,
    )
    back = progress.set_level(plan, step.exercise_id, _exercise(plan, "kb-swing").ladder[0].id)
    assert back is not None
    assert (back.outcome, back.warning) == (MoveOutcome.LEVEL_SET, None)


def test_a_locked_level_can_be_chosen_with_a_warning(plan: Session) -> None:
    equipment.save(plan, [KB8], NOW)
    exercise = _exercise(plan, "kb-swing")
    move = progress.set_level(plan, exercise.id, exercise.ladder[2].id)
    assert move is not None
    assert move.outcome is MoveOutcome.LEVEL_SET
    assert move.warning == "Two-hand, 16 kg needs a 16 kg kettlebell, not in your kit."
    assert _on(plan, exercise.id) == exercise.ladder[2].id
    back = progress.set_level(plan, exercise.id, exercise.ladder[0].id)
    assert back is not None
    assert back.warning is None


BERLIN = ZoneInfo("Europe/Berlin")
NOTED = datetime(2026, 10, 22, 10, tzinfo=UTC)  # a Thursday


def _top_noted(session: Session, slug: str, position: int) -> None:
    """The ready rule met at ``position`` with nothing open above it, saved on NOTED."""
    step = _put(session, slug, position)
    (item,) = progress.feedback(session, _ready(session, step))
    assert (item.status, item.note_top) == (Progress.TOP_OF_LADDER, True)
    event = session.scalars(select(Event).where(Event.kind == progress.TOP_NOTED)).one()
    event.at = NOTED
    session.flush()


def test_home_and_the_review_name_the_top_for_the_kit(plan: Session) -> None:
    """Like the saved screen and /progress (ADR-0078): the ready rule met with the next level
    locked by kit, naming what opens it, said in the week it was first met."""
    equipment.save(plan, [KB8], NOW)
    _top_noted(plan, "kb-swing", 1)
    swing = progress.Top(
        "Kettlebell swing", "kb-swing", "a 16 kg kettlebell unlocks Two-hand, 16 kg"
    )
    assert home.home(plan, date(2026, 10, 25), BERLIN).progress.top == [swing]
    assert home.home(plan, date(2026, 10, 25), BERLIN).progress.ready == []
    assert review.weekly(plan, date(2026, 10, 25), BERLIN).top == [swing]
    # Said once: not on Home after its 7 days, nor in the next week's review.
    assert home.home(plan, date(2026, 10, 29), BERLIN).progress.top == []
    assert review.weekly(plan, date(2026, 10, 26), BERLIN).top == []
    assert review.weekly(plan, date(2026, 10, 25)).top == []  # no time zone, no week to place it
    # The kettlebell arrives: ready to move up, no longer at the top.
    equipment.save(plan, [KB8, KB16], NOW)
    found = home.home(plan, date(2026, 10, 25), BERLIN).progress
    assert (found.top, [r.slug for r in found.ready]) == ([], ["kb-swing"])


def test_home_names_the_top_of_the_ladder(plan: Session) -> None:
    _top_noted(plan, "kb-swing", 4)  # Two-hand, 24 kg; no kit listed, so nothing locks
    assert home.home(plan, date(2026, 10, 22), BERLIN).progress.top == [
        progress.Top("Kettlebell swing", "kb-swing", None)
    ]


def test_a_top_noted_at_another_level_is_not_said_again(plan: Session) -> None:
    """The note belongs to the level it was met at: back down a level, the exercise isn't there."""
    _top_noted(plan, "kb-swing", 4)
    _put(plan, "kb-swing", 3)
    assert home.home(plan, date(2026, 10, 22), BERLIN).progress.top == []
