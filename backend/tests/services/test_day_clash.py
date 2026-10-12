"""A log for a day that already has its session (ADR-0060): asked first, then replaced, moved
or added, as one change /undo takes back."""

from collections.abc import Iterator
from datetime import UTC, date, datetime, time, timedelta

import pytest
import time_machine
from sqlalchemy import select
from sqlalchemy.orm import Session

from tests.services.test_today import PLAN
from tests.services.test_workout_log import BERLIN, TODAY
from training_coach.db.models import (
    Event,
    ImportedWorkout,
    PlanState,
    ReplacedWorkout,
    SessionProgress,
    SessionTemplate,
    SetLog,
    Workout,
)
from training_coach.domain.enums import WorkoutStatus
from training_coach.domain.queue import DoneOn
from training_coach.services import day_clash, undo, workout_log
from training_coach.services.day_clash import Clash, Recorded, Refused, Resolution
from training_coach.services.seed import apply_seed, load_plan

NOON = datetime.combine(TODAY, time(12), BERLIN)


@pytest.fixture(autouse=True)
def _midday() -> Iterator[None]:
    with time_machine.travel(NOON, tick=False):
        yield


# The optional rest session is "Easy day" here, so a plain "rest" names no session.
EASY = PLAN.replace('name = "Rest"', 'name = "Easy day"').replace('slug = "rest"', 'slug = "easy"')


@pytest.fixture
def seeded(session: Session) -> Session:
    apply_seed(session, load_plan(EASY))
    session.flush()
    return session


def _ids(session: Session) -> dict[str, int]:
    return {t.slug: t.id for t in session.scalars(select(SessionTemplate))}


def _pointer(session: Session) -> int | None:
    return session.get_one(PlanState, 1).next_template_id


def _ago(days: int) -> date:
    return TODAY - timedelta(days=days)


def _past(session: Session, days: int, text: str) -> workout_log.Draft:
    return workout_log.draft(session, f"{_ago(days):%Y-%m-%d} {text}", TODAY, BERLIN)


def _saved(session: Session, draft: workout_log.Draft, answer: Resolution | None = None) -> int:
    found = workout_log.save(session, draft, BERLIN, answer)
    assert isinstance(found, workout_log.Saved), found
    return found.workout_id


def _on(session: Session, day: date) -> list[tuple[int | None, str]]:
    rows = session.execute(
        select(Workout.template_id, Workout.status)
        .where(Workout.local_date == day)
        .order_by(Workout.id)
    )
    return [(t, s) for t, s in rows]


def _clash(session: Session, draft: workout_log.Draft) -> Clash:
    found = workout_log.save(session, draft, BERLIN)
    assert isinstance(found, Clash), found
    return found


def test_a_session_for_a_day_that_has_one_asks_and_writes_nothing(seeded: Session) -> None:
    ids = _ids(seeded)
    first = _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 8 7, split squat 10 10"))
    before = _pointer(seeded)
    found = _clash(seeded, _past(seeded, 2, "Zone 2\nzone 2 run 40"))
    assert found == Clash(_ago(2), (Recorded(first, "Upper", "5 sets: Pull-up, Split squat"),))
    assert _on(seeded, _ago(2)) == [(ids["upper"], WorkoutStatus.DONE)]
    assert _pointer(seeded) == before


@pytest.mark.parametrize(
    ("there", "shown"),
    [
        pytest.param("Zone 2\nzone 2 run 45", ("Zone 2", "45 min"), id="cardio-minutes"),
        pytest.param("Upper rest", ("Upper", "rested"), id="rested-session"),
        pytest.param("rest", ("Rest day", "rested"), id="rest-day"),
    ],
)
def test_the_question_says_what_is_there(
    seeded: Session, there: str, shown: tuple[str, str]
) -> None:
    _saved(seeded, _past(seeded, 3, there))
    found = _clash(seeded, _past(seeded, 3, "Upper\npull-ups 8"))
    assert [(r.name, r.summary) for r in found.recorded] == [shown]


def test_a_rest_day_on_a_day_with_a_session_asks(seeded: Session) -> None:
    _saved(seeded, _past(seeded, 1, "Upper\npull-ups 8"))
    assert isinstance(workout_log.save(seeded, _past(seeded, 1, "rest"), BERLIN), Clash)


def test_extras_never_ask(seeded: Session) -> None:
    _saved(seeded, _past(seeded, 1, "Upper\npull-ups 8"))
    extra = workout_log.Draft(
        token="ab" * 16,
        on=_ago(1),
        template_id=None,
        session_name=workout_log.EXTRA,
        entries=_past(seeded, 1, "Zone 2\nzone 2 run 30").entries,
        problems=(),
        backdated=True,
    )
    _saved(seeded, extra)
    assert len(_on(seeded, _ago(1))) == 2


def test_skipped_sessions_dont_count_as_the_days_session(seeded: Session) -> None:
    seeded.add(Workout(local_date=_ago(1), template_id=_ids(seeded)["upper"], status="skipped"))
    seeded.flush()
    _saved(seeded, _past(seeded, 1, "Upper\npull-ups 8"))


def test_replace_sets_the_old_one_aside_and_saves_the_new_one(seeded: Session) -> None:
    ids = _ids(seeded)
    _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 8"))
    draft = _past(seeded, 2, "Zone 2\nzone 2 run 40")
    found = _clash(seeded, draft)
    new = _saved(seeded, draft, Resolution(day_clash.REPLACE, found.ids))
    assert _on(seeded, _ago(2)) == [(ids["zone2"], WorkoutStatus.DONE)]
    kept = seeded.scalars(select(ReplacedWorkout)).one()
    assert (kept.local_date, kept.data["template_id"], len(kept.data["sets"])) == (
        _ago(2),
        ids["upper"],
        2,
    )
    event = seeded.scalars(select(Event).where(Event.kind == "workout.logged")).all()[-1]
    assert event.payload["resolved"] == "replace"
    assert event.payload["undo"]["removed"] == [kept.id]
    assert event.payload["workout_id"] == new


def test_move_puts_the_old_one_on_another_day_with_its_sets(seeded: Session) -> None:
    ids = _ids(seeded)
    old = _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 8"))
    draft = _past(seeded, 2, "Zone 2\nzone 2 run 40")
    found = _clash(seeded, draft)
    _saved(seeded, draft, Resolution(day_clash.MOVE, found.ids, _ago(4)))
    assert _on(seeded, _ago(2)) == [(ids["zone2"], WorkoutStatus.DONE)]
    moved = seeded.get_one(Workout, old)
    assert (moved.local_date, len(moved.sets)) == (_ago(4), 2)


def test_add_keeps_both(seeded: Session) -> None:
    ids = _ids(seeded)
    _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 8"))
    draft = _past(seeded, 2, "Zone 2\nzone 2 run 40")
    found = _clash(seeded, draft)
    _saved(seeded, draft, Resolution(day_clash.ADD, found.ids))
    assert [t for t, _ in _on(seeded, _ago(2))] == [ids["upper"], ids["zone2"]]


def test_a_day_that_changed_since_the_question_asks_again(seeded: Session) -> None:
    _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 8"))
    draft = _past(seeded, 2, "Zone 2\nzone 2 run 40")
    seen = _clash(seeded, draft)
    other = _saved(seeded, _past(seeded, 2, "Upper rest"), Resolution(day_clash.ADD, seen.ids))
    again = workout_log.save(seeded, draft, BERLIN, Resolution(day_clash.REPLACE, seen.ids))
    assert isinstance(again, Clash)
    assert other in again.ids
    assert len(_on(seeded, _ago(2))) == 2  # nothing replaced that the person didn't see


def test_moving_onto_a_day_with_a_session_asks_for_another_day(seeded: Session) -> None:
    _saved(seeded, _past(seeded, 4, "Zone 2\nzone 2 run 40"))
    _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 8"))
    draft = _past(seeded, 2, "Zone 2 rest")
    found = _clash(seeded, draft)
    there = workout_log.save(seeded, draft, BERLIN, Resolution(day_clash.MOVE, found.ids, _ago(4)))
    assert isinstance(there, Clash)
    assert (there.day, there.moving, [r.name for r in there.recorded]) == (
        _ago(4),
        True,
        ["Zone 2"],
    )
    assert len(_on(seeded, _ago(2))) == 1


@pytest.mark.parametrize(
    ("to", "reason"),
    [
        pytest.param(2, day_clash.SAME_DAY, id="same-day"),
        pytest.param(-1, "hasn't happened yet", id="future"),
        pytest.param(15, "more than 14 days ago", id="too-old"),
        pytest.param(None, day_clash.SAME_DAY, id="no-day"),
    ],
)
def test_a_move_that_cant_be_done_is_refused(seeded: Session, to: int | None, reason: str) -> None:
    _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 8"))
    draft = _past(seeded, 2, "Zone 2\nzone 2 run 40")
    found = _clash(seeded, draft)
    day = _ago(to) if to is not None else None
    refused = workout_log.save(seeded, draft, BERLIN, Resolution(day_clash.MOVE, found.ids, day))
    assert isinstance(refused, Refused)
    assert reason in refused.reason
    assert len(_on(seeded, _ago(2))) == 1


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("replace", Resolution("replace", (1, 2))),
        ("add", Resolution("add", (1, 2))),
        ("move:2026-10-06", Resolution("move", (1, 2), date(2026, 10, 6))),
        ("move:2026-02-30", None),
        ("delete", None),
    ],
)
def test_answers_are_read_strictly(answer: str, expected: Resolution | None) -> None:
    assert day_clash.parse(answer, [1, 2]) == expected


def test_latest_done_ignores_extras_rest_days_and_skips(seeded: Session) -> None:
    ids = _ids(seeded)
    assert day_clash.latest_done(seeded) is None
    upper = _saved(seeded, _past(seeded, 3, "Upper\npull-ups 8"))
    _saved(seeded, _past(seeded, 2, "rest"))
    seeded.add(Workout(local_date=_ago(1), template_id=ids["zone2"], status="skipped"))
    seeded.flush()
    assert day_clash.latest_done(seeded) == DoneOn(_ago(3), ids["upper"], upper)


# ------------------------------------------------------------ the queue (ADR-0060)


def test_the_8_october_scenario(seeded: Session) -> None:
    """Legs logged live on day N, then backdated to N-1, then a rest day backdated to N: the
    question offers N's Legs, and either answer leaves Legs counted once."""
    ids = _ids(seeded)
    n = _ago(1)
    live = workout_log.draft(seeded, "pull-ups 8 8, split squat 10 10", n, BERLIN)
    assert live.template_id == ids["upper"]
    on_n = _saved(seeded, live)
    assert _pointer(seeded) == ids["zone2"]
    _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 8, split squat 10 10"))
    assert _pointer(seeded) == ids["zone2"]  # a day before a logged one: history only
    rest = _past(seeded, 1, "rest")
    found = _clash(seeded, rest)
    assert found.recorded == (Recorded(on_n, "Upper", "4 sets: Pull-up, Split squat"),)
    _saved(seeded, rest, Resolution(day_clash.REPLACE, found.ids))
    assert _on(seeded, n) == [(None, WorkoutStatus.REST)]
    assert _pointer(seeded) == ids["zone2"]  # caught up after N-1's Upper, counted once


def test_the_8_october_scenario_moving_the_session(seeded: Session) -> None:
    ids = _ids(seeded)
    on_n = _saved(seeded, workout_log.draft(seeded, "pull-ups 8 8", _ago(1), BERLIN))
    _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 8"))
    rest = _past(seeded, 1, "rest")
    found = _clash(seeded, rest)
    _saved(seeded, rest, Resolution(day_clash.MOVE, found.ids, _ago(3)))
    assert seeded.get_one(Workout, on_n).local_date == _ago(3)
    assert _pointer(seeded) == ids["zone2"]


def test_replacing_the_latest_session_catches_up_to_the_new_one(seeded: Session) -> None:
    ids = _ids(seeded)
    _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8"))
    assert _pointer(seeded) == ids["zone2"]
    seeded.get_one(PlanState, 1).queued = [ids["upper"]]  # a swap since, dropped by catching up
    draft = _past(seeded, 2, "Zone 2\nzone 2 run 40")
    _saved(seeded, draft, Resolution(day_clash.REPLACE, _clash(seeded, draft).ids))
    assert (_pointer(seeded), seeded.get_one(PlanState, 1).queued) == (ids["easy"], [])


def test_replacing_an_older_day_leaves_the_queue(seeded: Session) -> None:
    ids = _ids(seeded)
    _saved(seeded, _past(seeded, 3, "Upper\npull-ups 8"))
    _saved(seeded, _past(seeded, 1, "Zone 2\nzone 2 run 40"))
    seeded.get_one(PlanState, 1).queued = [ids["upper"]]
    draft = _past(seeded, 3, "rest")
    _saved(seeded, draft, Resolution(day_clash.REPLACE, _clash(seeded, draft).ids))
    assert (_pointer(seeded), seeded.get_one(PlanState, 1).queued) == (ids["easy"], [ids["upper"]])


def test_replacing_the_only_session_with_a_rest_day_puts_it_next_again(seeded: Session) -> None:
    ids = _ids(seeded)
    _saved(seeded, _past(seeded, 1, "Upper\npull-ups 8"))
    draft = _past(seeded, 1, "rest")
    _saved(seeded, draft, Resolution(day_clash.REPLACE, _clash(seeded, draft).ids))
    assert _pointer(seeded) == ids["upper"]


def test_add_moves_the_queue_by_the_usual_rule(seeded: Session) -> None:
    ids = _ids(seeded)
    _saved(seeded, _past(seeded, 1, "Upper\npull-ups 8"))
    draft = _past(seeded, 1, "Zone 2\nzone 2 run 40")
    _saved(seeded, draft, Resolution(day_clash.ADD, _clash(seeded, draft).ids))
    assert _pointer(seeded) == ids["easy"]  # nothing later: caught up after it (ADR-0033)


# --------------------------------------------------------------------- one undo


def _undo(session: Session) -> undo.Undone | undo.Blocked:
    now = datetime.now(UTC)
    found = undo.last(session, now)
    assert isinstance(found, undo.Undoable), found
    return undo.apply(session, found.event_id, now)


def test_undoing_a_replace_puts_the_old_workout_back(seeded: Session) -> None:
    ids = _ids(seeded)
    old = _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 7"))
    old_token = seeded.get_one(Workout, old).log_token
    sets = [(s.exercise_id, s.set_no, s.value) for s in seeded.get_one(Workout, old).sets]
    pointer = _pointer(seeded)
    draft = _past(seeded, 2, "Zone 2\nzone 2 run 40")
    _saved(seeded, draft, Resolution(day_clash.REPLACE, _clash(seeded, draft).ids))
    found = undo.last(seeded, datetime.now(UTC))
    assert isinstance(found, undo.Undoable)
    assert found.what.endswith("(1 sets), which replaced Upper")
    _undo(seeded)
    assert _on(seeded, _ago(2)) == [(ids["upper"], WorkoutStatus.DONE)]
    back = seeded.scalars(select(Workout).where(Workout.local_date == _ago(2))).one()
    assert back.log_token == old_token
    assert [(s.exercise_id, s.set_no, s.value) for s in back.sets] == sets
    assert _pointer(seeded) == pointer
    assert seeded.scalars(select(ReplacedWorkout)).all() == []


def test_undoing_a_replace_links_the_band_workout_again(seeded: Session) -> None:
    old = _saved(seeded, _past(seeded, 2, "Zone 2\nzone 2 run 40"))
    band = ImportedWorkout(
        source="ab" * 8,
        start_at=NOON,
        end_at=NOON,
        local_date=_ago(2),
        exercise_type=56,
        activity="walk",
        minutes=40,
        status="counted",
        workout_id=old,
    )
    seeded.add(band)
    seeded.flush()
    draft = _past(seeded, 2, "Upper\npull-ups 8")
    _saved(seeded, draft, Resolution(day_clash.REPLACE, _clash(seeded, draft).ids))
    seeded.refresh(band)
    assert band.workout_id is None
    _undo(seeded)
    seeded.refresh(band)
    back = seeded.scalars(select(Workout).where(Workout.template_id == _ids(seeded)["zone2"]))
    assert band.workout_id == back.one().id


def test_undoing_a_move_puts_it_back(seeded: Session) -> None:
    old = _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 7"))
    draft = _past(seeded, 2, "Zone 2 rest")
    found = _clash(seeded, draft)
    _saved(seeded, draft, Resolution(day_clash.MOVE, found.ids, _ago(5)))
    last = undo.last(seeded, datetime.now(UTC))
    assert isinstance(last, undo.Undoable)
    assert last.what.endswith(f"which moved Upper to {_ago(5):%a %d %b}")
    _undo(seeded)
    assert seeded.get_one(Workout, old).local_date == _ago(2)
    assert len(_on(seeded, _ago(2))) == 1


def test_a_moved_workout_moved_again_blocks_the_undo(seeded: Session) -> None:
    old = _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 7"))
    draft = _past(seeded, 2, "Zone 2 rest")
    _saved(seeded, draft, Resolution(day_clash.MOVE, _clash(seeded, draft).ids, _ago(5)))
    seeded.get_one(Workout, old).local_date = _ago(6)
    seeded.flush()
    assert undo.last(seeded, datetime.now(UTC)) == undo.Blocked(undo.CHANGED)


def test_a_replaced_workout_saved_again_blocks_the_undo(seeded: Session) -> None:
    first = _past(seeded, 2, "Upper\npull-ups 8 7")
    _saved(seeded, first)
    draft = _past(seeded, 2, "Zone 2 rest")
    _saved(seeded, draft, Resolution(day_clash.REPLACE, _clash(seeded, draft).ids))
    kept = seeded.scalars(select(ReplacedWorkout)).one()
    seeded.add(Workout(local_date=_ago(9), status="done", log_token=kept.data["log_token"]))
    seeded.flush()
    assert undo.last(seeded, datetime.now(UTC)) == undo.Blocked(undo.CHANGED)
    seeded.delete(kept)
    seeded.flush()
    assert undo.last(seeded, datetime.now(UTC)) == undo.Blocked(undo.CHANGED)


def test_a_guided_sessions_progress_goes_with_a_replaced_or_moved_workout(
    seeded: Session,
) -> None:
    old = _saved(seeded, _past(seeded, 2, "Upper\npull-ups 8 7"))
    seeded.add(
        SessionProgress(
            local_date=_ago(2),
            template_id=_ids(seeded)["upper"],
            token="cd" * 16,
            saved_workout_id=old,
        )
    )
    seeded.flush()
    draft = _past(seeded, 2, "Zone 2 rest")
    _saved(seeded, draft, Resolution(day_clash.MOVE, _clash(seeded, draft).ids, _ago(5)))
    assert seeded.scalars(select(SessionProgress)).all() == []


def test_replaced_workouts_are_forgotten_after_a_day(seeded: Session) -> None:
    for days in (3, 2):
        _saved(seeded, _past(seeded, days, "Upper\npull-ups 8"))
        draft = _past(seeded, days, "rest")
        _saved(seeded, draft, Resolution(day_clash.REPLACE, _clash(seeded, draft).ids))
    assert len(seeded.scalars(select(ReplacedWorkout)).all()) == 2
    day_clash.sweep(seeded, datetime.now(UTC) + day_clash.KEPT + timedelta(seconds=1))
    assert seeded.scalars(select(ReplacedWorkout)).all() == []
    assert seeded.scalars(select(SetLog)).all() == []


def test_any_save_forgets_replaced_workouts_past_the_undo_window(seeded: Session) -> None:
    """Review of #240: the sweep ran only inside another replace or move, so a replaced
    workout and its sets could stay (and be exported) for weeks."""
    _saved(seeded, _past(seeded, 3, "Upper\npull-ups 8"))
    draft = _past(seeded, 3, "rest")
    _saved(seeded, draft, Resolution(day_clash.REPLACE, _clash(seeded, draft).ids))
    with time_machine.travel(NOON + day_clash.KEPT + timedelta(minutes=1), tick=False):
        _saved(seeded, _past(seeded, 1, "Zone 2\nzone 2 run 30"))  # an unrelated save
    assert seeded.scalars(select(ReplacedWorkout)).all() == []


def test_a_save_within_the_undo_window_keeps_it(seeded: Session) -> None:
    _saved(seeded, _past(seeded, 3, "Upper\npull-ups 8"))
    draft = _past(seeded, 3, "rest")
    _saved(seeded, draft, Resolution(day_clash.REPLACE, _clash(seeded, draft).ids))
    _saved(seeded, _past(seeded, 1, "Zone 2\nzone 2 run 30"))
    assert len(seeded.scalars(select(ReplacedWorkout)).all()) == 1
