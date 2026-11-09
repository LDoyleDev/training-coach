"""The walk-through's one save (ADR-0092): a member's plan made from what they chose, in one
transaction, touching no one else's rows and never the owner's plan."""

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from training_coach.db.models import (
    Equipment,
    Event,
    Exercise,
    ExerciseState,
    LadderStep,
    PlanState,
    PlanVersion,
    SessionProgress,
    SessionTemplate,
    TemplateItem,
    User,
    UserSettings,
    WalkthroughAnswers,
    Workout,
)
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.domain.consent import Category
from training_coach.domain.enums import Places
from training_coach.domain.kit import Item
from training_coach.domain.muscles import Kit
from training_coach.domain.step_levels import Mark
from training_coach.domain.walkthrough import Answers, CanDo
from training_coach.services import consent, plan_edit, users, walkthrough
from training_coach.services.seed import apply_seed, bundled_plan
from training_coach.services.walkthrough import Applied, Setup

TODAY = date(2026, 11, 9)
NOW = datetime(2026, 11, 9, 9, tzinfo=UTC)
MEMBER, OTHER = 2, 3
ROWS = (
    SessionTemplate,
    TemplateItem,
    PlanVersion,
    PlanState,
    ExerciseState,
    UserSettings,
    Equipment,
    WalkthroughAnswers,
)
ALL = {ALL_USERS: True}  # the test reads each person's rows by their id, to compare them


@pytest.fixture
def two(engine: Engine) -> Engine:
    """Two members on the 3-day starter, every exercise at its bottom step, and the owner."""
    with session_scope(make_session_factory(engine)) as shared:
        shared.add_all([User(id=MEMBER, role=users.MEMBER), User(id=OTHER, role=users.MEMBER)])
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, bundled_plan())
    return engine


def _rows(engine: Engine, user: int) -> dict[str, list[tuple[Any, ...]]]:
    """Every row of a person's plan, queue, levels, settings, kit and answers."""
    found: dict[str, list[tuple[Any, ...]]] = {}
    with make_session_factory(engine)() as shared:
        for model in ROWS:
            table = model.__table__  # type: ignore[attr-defined]  # every model has one
            columns = [c for c in table.columns if c.key != "updated_at"]
            query = select(*columns).where(table.c.user_id == user)
            rows = shared.execute(query.order_by(*table.primary_key.columns), execution_options=ALL)
            found[model.__name__] = [tuple(r) for r in rows]
    return found


def _step(session: Session, slug: str, name: str) -> int:
    return session.scalars(
        select(LadderStep.id).join(Exercise).where(Exercise.slug == slug, LadderStep.name == name)
    ).one()


def _on(session: Session, slug: str) -> str:
    return session.scalars(
        select(LadderStep.name)
        .join(ExerciseState, ExerciseState.ladder_step_id == LadderStep.id)
        .join(Exercise, Exercise.id == ExerciseState.exercise_id)
        .where(Exercise.slug == slug)
    ).one()


def _items(session: Session) -> dict[str, list[tuple[str, int | None]]]:
    return {
        t.slug: [(i.exercise.slug, i.pair) for i in t.items] for t in plan_edit.templates(session)
    }


def _apply(engine: Engine, setup: Setup, user: int = MEMBER, today: date = TODAY) -> Any:
    with session_scope(make_session_factory(engine, user_id=user)) as theirs:
        return walkthrough.apply(
            theirs, bundled_plan(), setup, plan_edit.revision(theirs), today, NOW
        )


def _setup(engine: Engine, **changes: Any) -> Setup:
    with make_session_factory(engine, user_id=MEMBER)() as mine:
        steps = {
            "push-up": _step(mine, "push-up", "Hands on a table"),
            "goblet-squat": _step(mine, "goblet-squat", "Sit to stand, arms crossed"),
        }
    return replace(Setup(starter="two-days", steps=steps, starts_on=TODAY), **changes)


def test_the_save_makes_the_members_plan_and_touches_no_one_elses(two: Engine) -> None:
    other, owner = _rows(two, OTHER), _rows(two, users.OWNER)
    setup = _setup(
        two, minutes=30, exercises=6, avoid=frozenset({Mark.FLOOR}), starts_on=date(2026, 11, 11)
    )
    applied = _apply(two, setup)
    assert isinstance(applied, Applied)
    assert applied.kept is False
    assert set(applied.moved) == {"Push-up", "Squat"}
    with session_scope(make_session_factory(two, user_id=MEMBER)) as mine:
        assert list(_items(mine)) == ["two-days-a", "two-days-b"]
        assert _on(mine, "push-up") == "Hands on a table"
        assert _on(mine, "plank") == "Hands on a counter"  # not sent: as it was
        state = mine.scalars(select(PlanState)).one()
        assert state.starts_on == date(2026, 11, 11)
        assert state.next_template_id == plan_edit.templates(mine)[0].id
        prefs = mine.scalars(select(UserSettings)).one()
        assert (prefs.session_minutes, prefs.session_exercises, prefs.avoid_floor) == (30, 6, True)
        assert prefs.set_up_on == TODAY
        versions = mine.scalars(select(PlanVersion.name).where(PlanVersion.since == TODAY))
        assert list(versions) == [walkthrough.NOTE]
        placed = mine.scalars(select(Event.payload).where(Event.kind == walkthrough.PLACED))
        assert all(set(p) == {"exercise_id", "from_step_id", "to_step_id"} for p in placed)
        assert applied.revision == plan_edit.revision(mine)
    assert _rows(two, OTHER) == other
    assert _rows(two, users.OWNER) == owner


def test_the_owner_is_refused_and_his_plan_untouched(two: Engine) -> None:
    owner = _rows(two, users.OWNER)
    with pytest.raises(PermissionError):
        _apply(two, _setup(two), user=users.OWNER)
    assert _rows(two, users.OWNER) == owner


def test_a_left_out_exercise_goes_from_every_version_and_its_pair_with_it(two: Engine) -> None:
    applied = _apply(two, _setup(two, left_out=frozenset({"bulgarian-split-squat"})))
    assert isinstance(applied, Applied)
    with session_scope(make_session_factory(two, user_id=MEMBER)) as mine:
        b = next(t for t in plan_edit.templates(mine) if t.slug == "two-days-b")
        assert [(i.exercise.slug, i.pair) for i in b.items][:2] == [
            ("push-up", None),
            ("glute-bridge", 2),
        ]
        assert "bulgarian-split-squat" not in {i.exercise.slug for i in b.away_items}


def test_a_session_left_with_nothing_is_refused(two: Engine) -> None:
    every = frozenset(walkthrough.ladders(bundled_plan()))
    assert "needs at least one exercise" in _apply(two, _setup(two, left_out=every))


def test_at_the_gym_the_gym_version_is_written_from_the_steps(two: Engine) -> None:
    with make_session_factory(two, user_id=MEMBER)() as mine:
        standard = _step(mine, "push-up", "Standard")
    setup = _setup(two, places=Places.BOTH, steps={"push-up": standard}, kit=())
    assert isinstance(_apply(two, setup), Applied)
    with session_scope(make_session_factory(two, user_id=MEMBER)) as mine:
        a = next(t for t in plan_edit.templates(mine) if t.slug == "two-days-a")
        assert "db-bench-press" in {i.exercise.slug for i in a.gym_items}
        assert mine.scalars(select(Equipment)).all() == []  # the kit sent: bodyweight only
        versions = mine.scalars(select(PlanVersion.name).where(PlanVersion.since == TODAY))
        assert list(versions) == [walkthrough.NOTE]  # one version, not the gym version's too


def test_a_locked_step_is_refused_and_nothing_changes(two: Engine) -> None:
    before = _rows(two, MEMBER)
    with make_session_factory(two, user_id=MEMBER)() as mine:
        standard = _step(mine, "push-up", "Standard")  # floor
    setup = _setup(two, steps={"push-up": standard}, avoid=frozenset({Mark.FLOOR}))
    assert "is locked" in _apply(two, setup)
    assert _rows(two, MEMBER) == before


def test_kit_locks_at_home_but_not_at_a_gym(two: Engine) -> None:
    with make_session_factory(two, user_id=MEMBER)() as mine:
        curl = {"kb-curl": _step(mine, "kb-curl", "8 kg")}
    assert "is locked" in _apply(two, _setup(two, steps=curl, kit=()))
    bell = (Item(Kit.KETTLEBELL, kg=8),)
    assert isinstance(_apply(two, _setup(two, steps=curl, kit=bell)), Applied)
    assert isinstance(_apply(two, _setup(two, steps=curl, places=Places.GYM, kit=())), Applied)


@pytest.mark.parametrize(
    ("changes", "why"),
    [
        ({"starter": "nine-days"}, "isn't a starter"),
        ({"minutes": 25}, "Minutes per session"),
        ({"exercises": 5}, "Exercises per session"),
        ({"starts_on": date(2026, 11, 16)}, "within the next week"),
        ({"starts_on": date(2026, 11, 8)}, "within the next week"),
        ({"steps": {"deadlift": 1}}, "not a step"),
        ({"steps": {"push-up": 1}}, "not a step"),  # the squat's bottom, not the push-up's
        ({"left_out": frozenset({"deadlift"})}, "Only the starters' exercises"),
        ({"kit": (Item(Kit.KETTLEBELL),)}, "say the weight"),
        ({"answers": Answers(placement={"deadlift": ((1, CanDo.YES),)})}, "isn't one of"),
    ],
)
def test_what_cant_be_saved_is_refused_in_words(
    two: Engine, changes: dict[str, Any], why: str
) -> None:
    before = _rows(two, MEMBER)
    found = _apply(two, _setup(two, **changes))
    assert isinstance(found, str)
    assert why in found
    assert _rows(two, MEMBER) == before


def test_once_a_workout_is_logged_it_is_closed(two: Engine) -> None:
    with session_scope(make_session_factory(two, user_id=MEMBER)) as mine:
        mine.add(Workout(local_date=TODAY, status="done", template_id=None))
    assert _apply(two, _setup(two)) == walkthrough.CLOSED
    with make_session_factory(two, user_id=OTHER)() as theirs:
        assert walkthrough.closed(theirs) is False


def test_a_session_in_progress_waits(two: Engine) -> None:
    with session_scope(make_session_factory(two, user_id=MEMBER)) as mine:
        first = plan_edit.templates(mine)[0].id
        kept = [{"item": 0, "set_no": 1, "left": 8}]
        mine.add(SessionProgress(local_date=TODAY, template_id=first, token="ab" * 16, sets=kept))
    assert _apply(two, _setup(two)) == walkthrough.IN_PROGRESS


def test_a_draft_of_an_older_plan_is_stale(two: Engine) -> None:
    with session_scope(make_session_factory(two, user_id=MEMBER)) as mine:
        found = walkthrough.apply(mine, bundled_plan(), _setup(two), "0" * 16, TODAY, NOW)
    assert found == walkthrough.STALE


def test_the_answers_are_kept_only_while_consent_is_open(two: Engine) -> None:
    answers = Answers(weekdays=(0, 3))
    assert _apply(two, _setup(two, answers=answers)).kept is False
    with session_scope(make_session_factory(two, user_id=MEMBER)) as mine:
        consent.give(mine, Category.WALKTHROUGH, NOW)
    assert _apply(two, _setup(two, answers=answers)).kept is True
    # Withdrawn after the route's check: the save reads consent again and keeps nothing.
    with session_scope(make_session_factory(two, user_id=MEMBER)) as mine:
        consent.withdraw(mine, Category.WALKTHROUGH, NOW)
    assert _apply(two, _setup(two, answers=answers)).kept is False
    assert _rows(two, MEMBER)["WalkthroughAnswers"] == []
    assert _rows(two, OTHER)["WalkthroughAnswers"] == []


def test_a_run_again_puts_the_plan_back_to_the_new_starter(two: Engine) -> None:
    assert isinstance(_apply(two, _setup(two, left_out=frozenset({"plank"}))), Applied)
    assert isinstance(_apply(two, _setup(two, starter="four-days")), Applied)
    with session_scope(make_session_factory(two, user_id=MEMBER)) as mine:
        assert len(_items(mine)) == 4
        assert any("plank" in [e for e, _ in items] for items in _items(mine).values())
        versions = mine.scalars(select(PlanVersion.name).where(PlanVersion.since == TODAY))
        assert list(versions) == [walkthrough.NOTE]


def test_a_starting_plan_from_today_is_replaced(two: Engine) -> None:
    joined = max(v.since for v in bundled_plan().versions)  # what "Starting plan" is dated
    setup = _setup(two, starts_on=joined)
    assert isinstance(_apply(two, setup, today=joined), Applied)
    with session_scope(make_session_factory(two, user_id=MEMBER)) as mine:
        names = list(mine.scalars(select(PlanVersion.name).order_by(PlanVersion.since)))
    assert names == [walkthrough.NOTE]
