from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tests.services.test_today import PLAN
from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    LadderStep,
    PlanState,
    SessionTemplate,
    SetLog,
    Workout,
)
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.queue import local_date
from training_coach.services import queue_actions, workout_log
from training_coach.services.seed import apply_seed, load_plan

BERLIN = ZoneInfo("Europe/Berlin")
TODAY = local_date(datetime.now(UTC), BERLIN)  # events are stamped with the real clock


@pytest.fixture
def seeded(session: Session) -> Session:
    apply_seed(session, load_plan(PLAN))
    session.flush()
    return session


def _ids(session: Session) -> dict[str, int]:
    return {t.slug: t.id for t in session.scalars(select(SessionTemplate))}


def _pointer(session: Session) -> int | None:
    state = session.get(PlanState, 1)
    assert state is not None
    return state.next_template_id


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_draft_targets_the_session_at_the_pointer(seeded: Session) -> None:
    draft = workout_log.draft(seeded, "pull-ups 8 8 7, split squat 10 10", TODAY, BERLIN)
    assert (draft.template_id, draft.session_name) == (_ids(seeded)["upper"], "Upper")
    assert [e.slug for e in draft.entries] == ["pull-up", "split-squat"]
    assert draft.problems == ()
    assert len(draft.token) == 32
    assert _count(seeded, Workout) == 0  # drafting never writes


def test_catalogue_knows_one_sided_work_from_the_plan(seeded: Session) -> None:
    known = {k.slug: k for k in workout_log.catalogue(seeded, None)}
    assert known["split-squat"].per_side
    assert not known["pull-up"].per_side
    assert known["run"].names == ("Zone 2 run",)


def test_save_writes_sets_at_the_current_step_and_moves_the_queue(seeded: Session) -> None:
    ids = _ids(seeded)
    draft = workout_log.draft(seeded, "pull-ups 8 7, split squat 10", TODAY, BERLIN)
    saved = workout_log.save(seeded, draft, BERLIN)
    assert saved is not None
    assert not saved.already_saved

    workout = seeded.get_one(Workout, saved.workout_id)
    assert (workout.status, workout.template_id, workout.local_date) == (
        "done",
        ids["upper"],
        TODAY,
    )
    pull_up = seeded.scalars(select(Exercise).where(Exercise.slug == "pull-up")).one()
    strict = seeded.get_one(ExerciseState, pull_up.id).ladder_step_id
    assert seeded.get_one(LadderStep, strict).name == "Strict"
    rows = sorted((s.exercise_id == pull_up.id, s.set_no, s.side, s.value) for s in workout.sets)
    assert rows == [
        (False, 1, Side.LEFT, 10),
        (False, 1, Side.RIGHT, 10),
        (True, 1, Side.BOTH, 8),
        (True, 2, Side.BOTH, 7),
    ]
    assert all(s.ladder_step_id == strict for s in workout.sets if s.exercise_id == pull_up.id)
    assert _pointer(seeded) == ids["zone2"]
    payloads = list(seeded.scalars(select(Event.payload).where(Event.kind == "workout.logged")))
    assert payloads == [
        {"workout_id": workout.id, "template_id": ids["upper"], "exercises": 2, "sets": 4}
    ]


def test_saving_the_same_draft_twice_changes_nothing(seeded: Session) -> None:
    """A double tap or a duplicate Telegram callback (from the review of #15)."""
    ids = _ids(seeded)
    draft = workout_log.draft(seeded, "pull-ups 8", TODAY, BERLIN)
    first = workout_log.save(seeded, draft, BERLIN)
    second = workout_log.save(seeded, draft, BERLIN)
    assert first is not None
    assert second is not None
    assert second == workout_log.Saved(first.workout_id, already_saved=True)
    assert _count(seeded, Workout) == 1
    assert _count(seeded, SetLog) == 1
    assert _pointer(seeded) == ids["zone2"]  # advanced once, not twice


def test_a_second_log_after_the_planned_session_is_an_extra(seeded: Session) -> None:
    ids = _ids(seeded)
    workout_log.save(seeded, workout_log.draft(seeded, "pull-ups 8", TODAY, BERLIN), BERLIN)
    extra = workout_log.draft(seeded, "run 30", TODAY, BERLIN)
    assert (extra.template_id, extra.session_name) == (None, "Extra session")
    workout_log.save(seeded, extra, BERLIN)
    assert _pointer(seeded) == ids["zone2"]  # extras never move the queue (ADR-0014)


def test_a_rested_session_also_makes_later_logs_extras(seeded: Session) -> None:
    rest = _ids(seeded)["rest"]
    state = seeded.get_one(PlanState, 1)
    state.next_template_id = rest
    queue_actions.rest_today(seeded, rest, TODAY)
    assert workout_log.target(seeded, TODAY, BERLIN) is None


def test_a_session_picked_today_is_the_target_and_keeps_the_queue(seeded: Session) -> None:
    ids = _ids(seeded)
    queue_actions.pick(seeded, ids["upper"], ids["zone2"])
    seeded.flush()
    draft = workout_log.draft(seeded, "run 45", TODAY, BERLIN)
    assert (draft.template_id, draft.session_name) == (ids["zone2"], "Zone 2")
    workout_log.save(seeded, draft, BERLIN)
    assert _pointer(seeded) == ids["upper"]  # out of order: upper is still next (ADR-0016)


def test_a_pick_from_yesterday_is_ignored(seeded: Session) -> None:
    ids = _ids(seeded)
    seeded.add(
        Event(
            kind="queue.picked",
            at=datetime.now(UTC) - timedelta(days=2),
            payload={"offered": ids["upper"], "picked": ids["zone2"]},
        )
    )
    seeded.flush()
    template = workout_log.target(seeded, TODAY, BERLIN)
    assert template is not None
    assert template.id == ids["upper"]


def test_a_draft_with_only_problems_saves_nothing(seeded: Session) -> None:
    draft = workout_log.draft(seeded, "burpees 10", TODAY, BERLIN)
    assert draft.entries == ()
    assert draft.problems
    assert workout_log.save(seeded, draft, BERLIN) is None
    assert _count(seeded, Workout) == 0


def test_no_plan_means_an_extra_and_no_queue_move(session: Session) -> None:
    apply_seed(session, load_plan(PLAN))
    session.get_one(PlanState, 1).next_template_id = None
    session.flush()
    draft = workout_log.draft(session, "pull-ups 5", TODAY, BERLIN)
    assert draft.template_id is None
    assert workout_log.save(session, draft, BERLIN) is not None


def test_only_done_workouts_carry_sets(seeded: Session) -> None:
    """Rest and skipped workouts are saved without sets (from the review of #15)."""
    ids = _ids(seeded)
    queue_actions.push_to_tomorrow(seeded, ids["upper"], TODAY)
    workout_log.save(seeded, workout_log.draft(seeded, "pull-ups 8", TODAY, BERLIN), BERLIN)
    seeded.flush()
    for workout in seeded.scalars(select(Workout)):
        assert bool(workout.sets) == (workout.status == WorkoutStatus.DONE)


def test_a_pick_of_a_missing_session_falls_back_to_the_pointer(seeded: Session) -> None:
    seeded.add(Event(kind="queue.picked", payload={"offered": 1, "picked": 999}))
    seeded.flush()
    template = workout_log.target(seeded, TODAY, BERLIN)
    assert template is not None
    assert template.id == _ids(seeded)["upper"]


# ------------------------------------------------------------- review of #52 (stale drafts)


def test_a_draft_remembers_its_day() -> None:
    assert "on" in workout_log.Draft.__dataclass_fields__


def test_a_draft_made_before_the_queue_moved_is_stale(seeded: Session) -> None:
    ids = _ids(seeded)
    draft = workout_log.draft(seeded, "pull-ups 8", TODAY, BERLIN)
    queue_actions.swap_next(seeded, ids["upper"])  # today's target is now Zone 2
    assert workout_log.save(seeded, draft, BERLIN) == workout_log.Stale()
    assert _count(seeded, Workout) == 0


def test_a_draft_naming_an_exercise_that_is_gone_is_stale(seeded: Session) -> None:
    draft = workout_log.draft(seeded, "pull-ups 8", TODAY, BERLIN)
    forged = workout_log.Draft(
        draft.token,
        draft.on,
        draft.template_id,
        draft.session_name,
        (workout_log.Entry("no-such-exercise", ((1, Side.BOTH, 5),)),),
        (),
    )
    assert workout_log.save(seeded, forged, BERLIN) == workout_log.Stale()
    assert _count(seeded, Workout) == 0


def test_a_draft_saved_after_midnight_keeps_its_day(seeded: Session) -> None:
    yesterday = TODAY - timedelta(days=1)
    draft = workout_log.draft(seeded, "pull-ups 8", yesterday, BERLIN)
    saved = workout_log.save(seeded, draft, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    assert seeded.get_one(Workout, saved.workout_id).local_date == yesterday


def test_a_pick_made_after_the_day_does_not_count_for_it(seeded: Session) -> None:
    ids = _ids(seeded)
    queue_actions.pick(seeded, ids["upper"], ids["zone2"])  # stamped now, i.e. today
    seeded.flush()
    template = workout_log.target(seeded, TODAY - timedelta(days=1), BERLIN)
    assert template is not None
    assert template.id == ids["upper"]


def test_a_racing_duplicate_save_reports_already_saved(
    seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two saves that both pass the token check: the database refuses the second insert."""
    ids = _ids(seeded)
    draft = workout_log.draft(seeded, "pull-ups 8", TODAY, BERLIN)
    winner = Workout(
        local_date=TODAY, template_id=None, status=WorkoutStatus.DONE, log_token=draft.token
    )
    seeded.add(winner)
    seeded.flush()
    real = workout_log._saved_before
    checks: list[str] = []

    def first_check_misses(session: Session, token: str) -> workout_log.Saved | None:
        checks.append(token)  # the first look happens before the other save commits
        return None if len(checks) == 1 else real(session, token)

    monkeypatch.setattr(workout_log, "_saved_before", first_check_misses)
    assert workout_log.save(seeded, draft, BERLIN) == workout_log.Saved(winner.id, True)
    assert _count(seeded, Workout) == 1
    assert _pointer(seeded) == ids["upper"]
