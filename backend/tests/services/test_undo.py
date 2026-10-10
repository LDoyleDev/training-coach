"""/undo (ADR-0048): the last rest, push, swap or saved log, taken back while nothing moved."""

from collections.abc import Iterator
from datetime import UTC, datetime, time, timedelta

import pytest
import time_machine
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.services.test_today import PLAN
from tests.services.test_workout_log import BERLIN, TODAY
from training_coach.db.models import Event, PlanState, SessionProgress, SessionTemplate, Workout
from training_coach.services import queue_actions, undo, workout_log
from training_coach.services.seed import apply_seed, load_plan

NOON = datetime.combine(TODAY, time(12), BERLIN)


@pytest.fixture(autouse=True)
def _midday() -> Iterator[None]:
    with time_machine.travel(NOON, tick=False):
        yield


@pytest.fixture
def seeded(session: Session) -> Session:
    apply_seed(session, load_plan(PLAN))
    session.flush()
    return session


def _now() -> datetime:
    return datetime.now(UTC)


def _ids(session: Session) -> dict[str, int]:
    return {t.slug: t.id for t in session.scalars(select(SessionTemplate))}


def _state(session: Session) -> tuple[int | None, list[int]]:
    state = session.get_one(PlanState, 1)
    return state.next_template_id, list(state.queued)


def _point_at(session: Session, slug: str) -> int:
    template_id = _ids(session)[slug]
    session.get_one(PlanState, 1).next_template_id = template_id
    session.flush()
    return template_id


def _workouts(session: Session) -> int:
    return len(list(session.scalars(select(Workout.id))))


def _undo(session: Session) -> undo.Undone | undo.Blocked:
    found = undo.last(session, _now())
    assert isinstance(found, undo.Undoable), found
    return undo.apply(session, found.event_id, _now())


def test_nothing_to_undo_on_a_fresh_plan(seeded: Session) -> None:
    assert undo.last(seeded, _now()) == undo.Blocked(undo.NOTHING)


def test_a_rest_day_is_taken_back(seeded: Session) -> None:
    held = _point_at(seeded, "zone2")
    before = _state(seeded)
    assert queue_actions.rest_today(seeded, held, TODAY) is not None
    found = undo.last(seeded, _now())
    assert isinstance(found, undo.Undoable)
    name = seeded.get_one(SessionTemplate, held).name
    assert found.what == f"the rest day for {name}"
    done = undo.apply(seeded, found.event_id, _now())
    assert done == undo.Undone(f"the rest day for {name}", name)
    assert _state(seeded) == before
    assert _workouts(seeded) == 0
    # One step only: the undo itself can't be undone, and the rest can't be undone twice.
    assert undo.last(seeded, _now()) == undo.Blocked(undo.NOTHING)
    assert undo.apply(seeded, found.event_id, _now()) == undo.Blocked(undo.NOTHING)


def test_an_optional_rest_that_moved_the_queue_moves_it_back(seeded: Session) -> None:
    rest = _point_at(seeded, "rest")
    queue_actions.rest_today(seeded, rest, TODAY)
    assert _state(seeded)[0] != rest
    assert isinstance(_undo(seeded), undo.Undone)
    assert _state(seeded) == (rest, [])
    assert _workouts(seeded) == 0


def test_a_push_is_taken_back(seeded: Session) -> None:
    held = _point_at(seeded, "zone2")
    queue_actions.push_to_tomorrow(seeded, held, TODAY)
    assert _workouts(seeded) == 1
    assert isinstance(_undo(seeded), undo.Undone)
    assert _workouts(seeded) == 0


def test_a_swap_is_taken_back(seeded: Session) -> None:
    offered = _point_at(seeded, "zone2")
    before = _state(seeded)
    queue_actions.swap_next(seeded, offered)
    assert _state(seeded) != before
    found = undo.last(seeded, _now())
    assert isinstance(found, undo.Undoable)
    assert found.what.startswith("doing ")
    undo.apply(seeded, found.event_id, _now())
    assert _state(seeded) == before


def test_a_saved_log_is_removed_and_the_queue_put_back(seeded: Session) -> None:
    before = _state(seeded)
    draft = workout_log.draft(seeded, "pull-ups 8 7, split squat 10", TODAY, BERLIN)
    saved = workout_log.save(seeded, draft, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    seeded.add(SessionProgress(local_date=TODAY, template_id=draft.template_id, token="t" * 32))
    seeded.flush()
    progress = seeded.scalars(select(SessionProgress)).one()
    progress.saved_workout_id = saved.workout_id
    found = undo.last(seeded, _now())
    assert isinstance(found, undo.Undoable)
    assert found.what.startswith(f"the Upper log for {TODAY:%a %d %b} (")
    undo.apply(seeded, found.event_id, _now())
    assert _state(seeded) == before
    assert _workouts(seeded) == 0
    assert progress.saved_workout_id is None  # the guided sets are kept, unsaved again


def test_a_change_since_blocks_the_undo(seeded: Session) -> None:
    offered = _point_at(seeded, "zone2")
    queue_actions.swap_next(seeded, offered)
    seeded.get_one(PlanState, 1).next_template_id = offered  # moved some other way
    seeded.flush()
    assert undo.last(seeded, _now()) == undo.Blocked(undo.CHANGED)


def test_a_removed_workout_blocks_the_undo(seeded: Session) -> None:
    held = _point_at(seeded, "zone2")
    queue_actions.push_to_tomorrow(seeded, held, TODAY)
    seeded.delete(seeded.scalars(select(Workout)).one())
    seeded.flush()
    assert undo.last(seeded, _now()) == undo.Blocked(undo.CHANGED)


def test_an_older_button_cannot_undo_a_newer_change(seeded: Session) -> None:
    held = _point_at(seeded, "zone2")
    queue_actions.push_to_tomorrow(seeded, held, TODAY)
    old = undo.last(seeded, _now())
    assert isinstance(old, undo.Undoable)
    queue_actions.swap_next(seeded, held)
    assert undo.apply(seeded, old.event_id, _now()) == undo.Blocked(undo.CHANGED)


def test_a_change_more_than_a_day_old_stays(seeded: Session) -> None:
    held = _point_at(seeded, "zone2")
    queue_actions.push_to_tomorrow(seeded, held, TODAY)
    later = _now() + undo.WINDOW + timedelta(minutes=1)
    assert undo.last(seeded, later) == undo.Blocked(undo.TOO_OLD)


def test_events_from_before_undo_existed_are_not_undone(seeded: Session) -> None:
    seeded.add(Event(kind="queue.rest", payload={"template_id": 1, "status": "skipped"}))
    seeded.flush()
    assert undo.last(seeded, _now()) == undo.Blocked(undo.NOTHING)
