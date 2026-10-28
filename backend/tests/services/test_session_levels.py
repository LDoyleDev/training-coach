"""Changing an exercise's level during the guided session (ADR-0080), against the bundled plan.

Legs is the first session; its first exercise, the jump squat, has three steps: "Bodyweight, full
rest", "Pause at bottom, then jump" and "Holding 8 kg" (needs an 8 kg kettlebell)."""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, Exercise, LadderStep, SessionProgress, Workout
from training_coach.domain.kit import parse_item
from training_coach.domain.load import LoadKit
from training_coach.services import blocks, equipment, guided, progress, users, workout_log
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.session_levels import (
    NOT_IN_SESSION,
    NOT_ON_LADDER,
    Changed,
    Scope,
    change,
    done_at,
    ladders,
    today_only,
)

BERLIN = ZoneInfo("Europe/Berlin")
DAY = date(2026, 10, 12)
JUMP = "jump-squat"


@pytest.fixture
def seeded(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _plan(session: Session) -> guided.Guided:
    plan = guided.today(session, DAY, BERLIN)
    assert plan is not None
    return plan


def _steps(session: Session) -> list[LadderStep]:
    jump = session.scalars(select(Exercise).where(Exercise.slug == JUMP)).one()
    return list(jump.ladder)


def _level(session: Session) -> int:
    jump = session.scalars(select(Exercise).where(Exercise.slug == JUMP)).one()
    state = users.exercise_state(session, jump.id)
    assert state is not None
    return state.ladder_step_id


def _saved_steps(session: Session) -> list[tuple[int, int]]:
    """(set number, ladder step id) of the jump squat's saved sets."""
    saved = guided.save(session, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    jump = session.scalars(select(Exercise).where(Exercise.slug == JUMP)).one()
    rows = session.get_one(Workout, saved.workout_id).sets
    return sorted((r.set_no, r.ladder_step_id) for r in rows if r.exercise_id == jump.id)


def test_for_today_saves_the_sets_at_the_chosen_step_and_leaves_the_level(
    seeded: Session,
) -> None:
    bottom, pause, _ = _steps(seeded)
    assert _level(seeded) == bottom.id
    changed = change(seeded, _plan(seeded), 0, JUMP, pause.id, Scope.TODAY)
    assert changed == Changed(revision=2, warning=None)  # started, then changed
    plan = _plan(seeded)  # as a reload sees it
    item = plan.items[0]
    assert (item.step, item.step_id, item.baseline) == (pause.name, pause.id, True)
    assert set(item.targets) == {5}  # no history at the step: the bottom of Legs' 5-8
    done = [guided.Done(0, 1, 7), guided.Done(0, 2, 6)]
    assert guided.keep(seeded, plan, 2, 2, [], done) == 3
    assert _saved_steps(seeded) == [(1, pause.id), (2, pause.id)]
    workout = seeded.scalars(select(Workout)).one()
    assert done_at(seeded, DAY, workout.id) == [("Jump squat", (pause.name,))]
    assert _level(seeded) == bottom.id
    assert not seeded.scalars(select(Event).where(Event.kind == progress.LEVEL_SET)).all()


def test_sets_already_confirmed_keep_the_step_they_were_done_at(seeded: Session) -> None:
    bottom, pause, _ = _steps(seeded)
    plan = _plan(seeded)
    assert guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 9)]) == 1
    assert change(seeded, plan, 1, JUMP, pause.id, Scope.TODAY) == Changed(2, None)
    done = [guided.Done(0, 1, 9), guided.Done(0, 2, 6)]  # the browser never sends a step
    assert guided.keep(seeded, _plan(seeded), 2, 2, [], done) == 3
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert [d.step_id for d in kept.sets] == [bottom.id, None]
    assert kept.steps == ((JUMP, pause.id),)
    assert _saved_steps(seeded) == [(1, bottom.id), (2, pause.id)]


def test_changing_twice_keeps_each_set_at_its_own_step(seeded: Session) -> None:
    bottom, pause, held = _steps(seeded)
    plan = _plan(seeded)
    guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 9)])
    change(seeded, plan, 1, JUMP, pause.id, Scope.TODAY)
    guided.keep(seeded, _plan(seeded), 2, 2, [], [guided.Done(0, 1, 9), guided.Done(0, 2, 6)])
    change(seeded, _plan(seeded), 3, JUMP, held.id, Scope.TODAY)
    sets = [guided.Done(0, 1, 9), guided.Done(0, 2, 6), guided.Done(0, 3, 5)]
    guided.keep(seeded, _plan(seeded), 4, 3, [], sets)
    assert _saved_steps(seeded) == [(1, bottom.id), (2, pause.id), (3, held.id)]


def test_from_now_on_sets_the_level_as_the_plan_tab_does(seeded: Session) -> None:
    bottom, pause, _ = _steps(seeded)
    plan = _plan(seeded)
    guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 9)])
    assert change(seeded, plan, 1, JUMP, pause.id, Scope.FROM_NOW_ON) == Changed(2, None)
    assert _level(seeded) == pause.id
    events = seeded.scalars(select(Event).where(Event.kind == progress.LEVEL_SET)).all()
    assert [e.payload["to_step_id"] for e in events] == [pause.id]
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert kept.steps == ((JUMP, pause.id),)  # today is at the step picked
    assert today_only(seeded, dict(kept.steps)) == set()  # and it is the level now
    assert _plan(seeded).items[0].step_id == pause.id
    guided.keep(seeded, _plan(seeded), 2, 2, [], [guided.Done(0, 1, 9), guided.Done(0, 2, 6)])
    assert _saved_steps(seeded) == [(1, bottom.id), (2, pause.id)]
    workout = seeded.scalars(select(Workout)).one()
    assert done_at(seeded, DAY, workout.id) == [("Jump squat", (bottom.name, pause.name))]


def test_nothing_changed_says_nothing_on_the_saved_screen(seeded: Session) -> None:
    guided.keep(seeded, _plan(seeded), 0, 1, [], [guided.Done(0, 1, 9)])
    assert _saved_steps(seeded) == [(1, _steps(seeded)[0].id)]
    workout = seeded.scalars(select(Workout)).one()
    assert done_at(seeded, DAY, workout.id) == []
    assert done_at(seeded, DAY.replace(day=1), workout.id) == []


def test_from_now_on_in_a_strength_block_does_the_picked_step_today(seeded: Session) -> None:
    """A strength session trains a step above the level (ADR-0028); the step picked is still
    the one done today, and the level is the one picked."""
    bottom, pause, held = _steps(seeded)
    row = users.settings_row(seeded)
    assert row is not None
    row.blocks_started_on = DAY  # the first strength block starts today
    seeded.flush()
    assert _plan(seeded).items[0].step_id == pause.id  # a step above the level
    assert change(seeded, _plan(seeded), 0, JUMP, pause.id, Scope.FROM_NOW_ON) == Changed(2, None)
    assert _level(seeded) == pause.id
    assert _plan(seeded).items[0].step_id == pause.id
    assert today_only(seeded, {JUMP: pause.id}) == set()
    assert change(seeded, _plan(seeded), 2, JUMP, bottom.id, Scope.TODAY) == Changed(3, None)
    assert _plan(seeded).items[0].step_id == bottom.id  # the strength rule doesn't add a step
    assert held.id not in {i.step_id for i in _plan(seeded).items}


def test_a_locked_level_is_chosen_with_a_warning(seeded: Session) -> None:
    *_, held = _steps(seeded)
    equipment.save(seeded, [parse_item("dumbbells:10")], datetime.now(UTC))
    changed = change(seeded, _plan(seeded), 0, JUMP, held.id, Scope.TODAY)
    assert isinstance(changed, Changed)
    assert changed.warning == "Holding 8 kg needs an 8 kg kettlebell, not in your kit."
    rungs = ladders(seeded, [JUMP, "tibialis-raise"])[JUMP]
    assert [r.missing for r in rungs] == [(), (), ("an 8 kg kettlebell",)]


def test_only_exercises_with_more_than_one_step_have_a_ladder(seeded: Session) -> None:
    found = ladders(seeded, [i.slug for i in _plan(seeded).items])
    assert JUMP in found
    singles = [
        e.slug for e in seeded.scalars(select(Exercise)) if len(e.ladder) == 1 and e.slug in found
    ]
    assert singles == []


@pytest.mark.parametrize(
    ("slug", "other", "problem"),
    [(JUMP, "tibialis-raise", NOT_ON_LADDER), ("dead-hang", "dead-hang", NOT_IN_SESSION)],
    ids=["another-exercises-step", "not-in-the-session"],
)
def test_a_step_off_the_ladder_or_session_changes_nothing(
    seeded: Session, slug: str, other: str, problem: str
) -> None:
    step = seeded.scalars(
        select(LadderStep).join(Exercise).where(Exercise.slug == other).limit(1)
    ).one()
    assert change(seeded, _plan(seeded), 0, slug, step.id, Scope.TODAY) == problem
    assert seeded.scalars(select(SessionProgress)).all() == []


def test_a_stale_browser_changes_nothing(seeded: Session) -> None:
    _, pause, _ = _steps(seeded)
    plan = _plan(seeded)
    assert change(seeded, plan, 3, JUMP, pause.id, Scope.TODAY) == guided.STALE  # nothing kept
    guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 9)])
    assert change(seeded, plan, 0, JUMP, pause.id, Scope.TODAY) == guided.STALE
    assert change(seeded, plan, 5, JUMP, pause.id, Scope.TODAY) == guided.STALE
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert (kept.steps, kept.revision) == ((), 1)


def test_a_saved_session_changes_no_more(seeded: Session) -> None:
    _, pause, _ = _steps(seeded)
    plan = _plan(seeded)
    guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 9)])
    assert isinstance(guided.save(seeded, DAY, DAY, BERLIN), workout_log.Saved)
    assert change(seeded, plan, 1, JUMP, pause.id, Scope.TODAY) == "this session is saved already"


def test_a_level_for_today_is_said_only_while_it_isnt_the_level(seeded: Session) -> None:
    bottom, pause, _ = _steps(seeded)
    assert today_only(seeded, {}) == set()
    assert today_only(seeded, {JUMP: pause.id, "gone": 1}) == {JUMP}
    assert today_only(seeded, {JUMP: bottom.id}) == set()


def test_a_step_not_on_the_ladder_is_never_saved(seeded: Session) -> None:
    """Checked again at saving: a step of another exercise in the kept progress is ignored."""
    bottom, _, _ = _steps(seeded)
    guided.keep(seeded, _plan(seeded), 0, 1, [], [guided.Done(0, 1, 9)])
    row = seeded.scalars(select(SessionProgress)).one()
    tibialis = seeded.scalars(
        select(LadderStep).join(Exercise).where(Exercise.slug == "tibialis-raise").limit(1)
    ).one()
    row.sets = [{**row.sets[0], "step_id": tibialis.id}]
    seeded.flush()
    assert _saved_steps(seeded) == [(1, bottom.id)]


def _loaded_at(monkeypatch: pytest.MonkeyPatch, step: str) -> None:
    """The jump squat as if only ``step`` of it took dumbbells (ADR-0072)."""
    monkeypatch.setattr(blocks, "_load_kits", lambda: {(JUMP, step): LoadKit.DUMBBELLS})


@pytest.mark.parametrize("loaded", [None, 2], ids=["no-step-loaded", "the-new-step-loaded"])
def test_a_weight_on_a_set_done_at_an_unloaded_earlier_level_is_refused(
    seeded: Session, monkeypatch: pytest.MonkeyPatch, loaded: int | None
) -> None:
    """A set kept at an earlier level is checked against that level, not the step shown now:
    the browser re-sends every set, so it could add a weight to one done without."""
    steps = _steps(seeded)
    if loaded is not None:
        _loaded_at(monkeypatch, steps[loaded].name)
    plan = _plan(seeded)
    assert guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 9)]) == 1
    assert isinstance(change(seeded, plan, 1, JUMP, steps[2].id, Scope.TODAY), Changed)
    done = [guided.Done(0, 1, 9, load_kg=10.0), guided.Done(0, 2, 6)]
    refused = guided.keep(seeded, _plan(seeded), 2, 2, [], done)
    assert refused == "Jump squat isn't done with a weight"
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert (kept.revision, [d.load_kg for d in kept.sets]) == (2, [None])


def test_a_weight_on_a_set_done_at_a_loaded_earlier_level_is_kept(
    seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    bottom, pause, _ = _steps(seeded)
    _loaded_at(monkeypatch, bottom.name)
    plan = _plan(seeded)
    assert plan.items[0].load is not None
    assert guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 9, load_kg=12.0)]) == 1
    assert change(seeded, plan, 1, JUMP, pause.id, Scope.TODAY) == Changed(2, None)
    assert _plan(seeded).items[0].load is None
    done = [guided.Done(0, 1, 9, load_kg=12.0), guided.Done(0, 2, 6)]
    assert guided.keep(seeded, _plan(seeded), 2, 2, [], done) == 3
    assert _saved_steps(seeded) == [(1, bottom.id), (2, pause.id)]
    workout = seeded.scalars(select(Workout)).one()
    assert sorted(r.load_kg for r in workout.sets if r.set_no == 1 and r.load_kg) == [12.0]
