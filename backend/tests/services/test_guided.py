"""The guided session's view of today (#117), against the bundled plan."""

from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import SessionProgress, SessionTemplate, Workout
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import guided, users, workout_log
from training_coach.services.seed import apply_seed, load_plan

BERLIN = ZoneInfo("Europe/Berlin")
DAY = date(2026, 10, 12)


def _seeded(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def test_today_is_the_queued_session_in_work_order(session: Session) -> None:
    plan = guided.today(_seeded(session), DAY, BERLIN)
    assert plan is not None
    assert (plan.name, plan.kind, plan.warm_up) == ("Legs", "strength", True)
    first_six = [plan.items[s.item].slug for s in plan.order[:6]]
    assert first_six == ["jump-squat", "tibialis-raise"] * 3
    assert len(plan.order) == sum(len(i.targets) for i in plan.items)
    assert all(s.target == plan.items[s.item].targets[s.set_no - 1] for s in plan.order)
    assert all(i.summary and i.slug for i in plan.items)
    assert plan.rest_seconds == guided.REST_SECONDS
    assert 40 <= plan.minutes <= 90  # warm-up plus 25 sets, some per side


def test_a_pair_can_start_with_its_second_exercise(session: Session) -> None:
    plan = guided.today(_seeded(session), DAY, BERLIN, first={1})
    assert plan is not None
    assert [plan.items[s.item].slug for s in plan.order[:2]] == ["tibialis-raise", "jump-squat"]


def test_nothing_to_guide_once_today_is_done(session: Session) -> None:
    seeded = _seeded(session)
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    seeded.add(Workout(local_date=DAY, template_id=plan.template_id, status=WorkoutStatus.DONE))
    seeded.flush()
    assert guided.today(seeded, DAY, BERLIN) is None


def test_a_cardio_session_has_no_warm_up_and_counts_its_minutes(session: Session) -> None:
    seeded = _seeded(session)
    zone2 = seeded.scalars(select(SessionTemplate).where(SessionTemplate.slug == "zone2")).one()
    state = users.plan_state(seeded)
    assert state is not None
    state.next_template_id = zone2.id
    seeded.flush()
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    assert (plan.name, plan.warm_up) == ("Long zone 2", False)
    (item,) = plan.items
    assert plan.minutes == item.targets[0]  # the walk itself, no warm-up or rests


def test_timed_sets_count_their_seconds(session: Session) -> None:
    seeded = _seeded(session)
    arms = seeded.scalars(select(SessionTemplate).where(SessionTemplate.slug == "arms")).one()
    state = users.plan_state(seeded)
    assert state is not None
    state.next_template_id = arms.id
    seeded.flush()
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    hang = next(i for i in plan.items if i.slug == "dead-hang")
    assert hang.kind.value == "seconds"
    assert plan.order[-1].item == plan.items.index(hang)  # alone, after the pairs


def _plan(session: Session) -> guided.Guided:
    plan = guided.today(session, DAY, BERLIN)
    assert plan is not None
    return plan


def test_progress_restarts_when_the_days_session_changes(session: Session) -> None:
    seeded = _seeded(session)
    legs = _plan(seeded)
    assert guided.keep(seeded, legs, 1, [], [guided.Done(0, 1, 5)]) is None
    torso = seeded.scalars(select(SessionTemplate).where(SessionTemplate.slug == "torso")).one()
    state = users.plan_state(seeded)
    assert state is not None
    state.next_template_id = torso.id  # as if swapped
    seeded.flush()
    assert guided.keep(seeded, _plan(seeded), 0, [], []) is None
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert (kept.template_id, kept.sets) == (torso.id, ())


def test_a_saved_session_is_not_kept_again(session: Session) -> None:
    seeded = _seeded(session)
    plan = _plan(seeded)
    guided.keep(seeded, plan, 1, [], [guided.Done(0, 1, 5)])
    assert isinstance(guided.save(seeded, DAY, DAY, BERLIN), workout_log.Saved)
    assert guided.keep(seeded, plan, 2, [], []) == "this session is saved already"


def test_sets_the_plan_no_longer_has_are_not_saved(session: Session) -> None:
    seeded = _seeded(session)
    guided.keep(seeded, _plan(seeded), 1, [], [guided.Done(0, 1, 5)])
    row = seeded.scalars(select(SessionProgress)).one()
    row.sets = [{"item": 0, "set_no": 9, "left": 5, "right": None}]  # the plan changed since
    seeded.flush()
    assert (
        guided.save(seeded, DAY, DAY, BERLIN) == "the plan changed since these sets were recorded"
    )


def test_an_earlier_day_with_no_sets_is_not_pending(session: Session) -> None:
    seeded = _seeded(session)
    guided.keep(seeded, _plan(seeded), 0, [], [])
    assert guided.pending(seeded, DAY.replace(day=DAY.day + 1)) == []


def test_keeping_again_updates_the_same_progress(session: Session) -> None:
    seeded = _seeded(session)
    plan = _plan(seeded)
    guided.keep(seeded, plan, 1, [], [guided.Done(0, 1, 5)])
    guided.keep(seeded, plan, 2, [1], [guided.Done(0, 1, 5), guided.Done(1, 1, 20)])
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert (kept.position, kept.first, len(kept.sets)) == (2, (1,), 2)
    assert len(seeded.scalars(select(SessionProgress)).all()) == 1
