"""The guided session's view of today (#117), against the bundled plan."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from training_coach.db.models import SessionProgress, SessionTemplate, Workout
from training_coach.db.session import make_session_factory
from training_coach.domain.enums import WorkoutStatus
from training_coach.services import guided, queue_actions, users, workout_log
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

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


def test_nothing_to_guide_once_today_is_held_for_tomorrow(session: Session) -> None:
    """Rest today or Push from either surface: the web shows nothing left today either."""
    seeded = _seeded(session)
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    assert queue_actions.push_to_tomorrow(seeded, plan.template_id, DAY) == plan.name
    assert guided.today(seeded, DAY, BERLIN) is None
    assert guided.today(seeded, date(2026, 10, 13), BERLIN) is not None  # it waits a day


def test_a_skipped_row_for_another_session_does_not_blank_the_day(session: Session) -> None:
    """Only a hold of the queue's own session counts: an extra or another session's skipped
    row (an import, an old hold before a swap) leaves today's session to guide."""
    seeded = _seeded(session)
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    other = seeded.scalars(select(SessionTemplate).where(SessionTemplate.slug == "zone2")).one()
    seeded.add(Workout(local_date=DAY, template_id=None, status=WorkoutStatus.SKIPPED))
    seeded.add(Workout(local_date=DAY, template_id=other.id, status=WorkoutStatus.SKIPPED))
    seeded.flush()
    assert not guided.held_today(seeded, DAY)
    found = guided.today(seeded, DAY, BERLIN)
    assert found is not None
    assert found.template_id == plan.template_id


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
    recovery = seeded.scalars(
        select(SessionTemplate).where(SessionTemplate.slug == "recovery")
    ).one()
    state = users.plan_state(seeded)
    assert state is not None
    state.next_template_id = recovery.id
    seeded.flush()
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    hang = next(i for i in plan.items if i.slug == "dead-hang")
    assert hang.kind.value == "seconds"
    paired = [plan.items[o.item].slug for o in plan.order]
    paired = [s for s in paired if s in ("dead-hang", "neck-extension")]
    assert paired == ["dead-hang", "neck-extension", "dead-hang"]  # its extra set alone


def _plan(session: Session) -> guided.Guided:
    plan = guided.today(session, DAY, BERLIN)
    assert plan is not None
    return plan


def test_progress_restarts_when_the_days_session_changes(session: Session) -> None:
    seeded = _seeded(session)
    legs = _plan(seeded)
    assert guided.keep(seeded, legs, 0, 1, [], [guided.Done(0, 1, 5)]) == 1
    torso = seeded.scalars(select(SessionTemplate).where(SessionTemplate.slug == "torso")).one()
    state = users.plan_state(seeded)
    assert state is not None
    state.next_template_id = torso.id  # as if swapped
    seeded.flush()
    assert guided.keep(seeded, _plan(seeded), 0, 0, [], []) == 1  # a fresh start
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert (kept.template_id, kept.sets) == (torso.id, ())


def test_a_saved_session_is_not_kept_again(session: Session) -> None:
    seeded = _seeded(session)
    plan = _plan(seeded)
    guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 5)])
    assert isinstance(guided.save(seeded, DAY, DAY, BERLIN), workout_log.Saved)
    assert guided.keep(seeded, plan, 1, 2, [], []) == "this session is saved already"


def test_sets_the_plan_no_longer_has_are_not_saved(session: Session) -> None:
    seeded = _seeded(session)
    guided.keep(seeded, _plan(seeded), 0, 1, [], [guided.Done(0, 1, 5)])
    row = seeded.scalars(select(SessionProgress)).one()
    row.sets = [{"item": 0, "set_no": 9, "left": 5, "right": None}]  # the plan changed since
    seeded.flush()
    assert (
        guided.save(seeded, DAY, DAY, BERLIN) == "the plan changed since these sets were recorded"
    )


def test_an_earlier_day_with_no_sets_is_not_pending(session: Session) -> None:
    seeded = _seeded(session)
    guided.keep(seeded, _plan(seeded), 0, 0, [], [])
    assert guided.pending(seeded, DAY.replace(day=DAY.day + 1)) == []


def test_keeping_again_updates_the_same_progress(session: Session) -> None:
    seeded = _seeded(session)
    plan = _plan(seeded)
    assert guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 5)]) == 1
    done = [guided.Done(0, 1, 5), guided.Done(1, 1, 20)]
    assert guided.keep(seeded, plan, 1, 2, [1], done) == 2
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert (kept.position, kept.first, len(kept.sets)) == (2, (1,), 2)
    assert len(seeded.scalars(select(SessionProgress)).all()) == 1


def test_a_stale_device_cannot_overwrite_newer_sets(session: Session) -> None:
    seeded = _seeded(session)
    plan = _plan(seeded)
    assert guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 5)]) == 1  # the phone
    assert guided.keep(seeded, plan, 0, 1, [], []) == guided.STALE  # a tab that saw nothing
    assert guided.keep(seeded, plan, 1, 2, [], [guided.Done(0, 1, 5), guided.Done(1, 1, 20)]) == 2
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert len(kept.sets) == 2


def test_a_first_save_naming_a_revision_is_stale(session: Session) -> None:
    seeded = _seeded(session)
    assert guided.keep(seeded, _plan(seeded), 3, 0, [], []) == guided.STALE


def test_a_skipped_set_is_not_logged_and_the_rest_are_numbered_from_one(session: Session) -> None:
    seeded = _seeded(session)
    plan = _plan(seeded)
    done = [guided.Done(0, 1, 6), guided.Done(0, 3, 4)]  # set 2 skipped
    guided.keep(seeded, plan, 0, 2, [], done)
    saved = guided.save(seeded, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    sets = seeded.get_one(Workout, saved.workout_id).sets
    assert sorted((s.set_no, s.value) for s in sets) == [(1, 6), (2, 4)]


def test_two_devices_starting_at_once_do_not_fail(engine: Engine) -> None:
    """Both see no progress yet; the unique day decides, and the loser is told it's stale."""
    with make_session_factory(engine, user_id=OWNER)() as setup:
        _seeded(setup)
        setup.commit()
    with make_session_factory(engine, user_id=OWNER)() as phone:
        plan = _plan(phone)
        assert guided.keep(phone, plan, 0, 0, [], []) == 1
        phone.commit()
    with make_session_factory(engine, user_id=OWNER)() as laptop:
        original = guided._row
        guided._row = lambda *_: None  # the laptop read "no progress" a moment earlier
        try:
            assert guided.keep(laptop, plan, 0, 0, [], []) == guided.STALE
        finally:
            guided._row = original


def test_a_stale_browser_on_an_old_session_deletes_nothing(session: Session) -> None:
    seeded = _seeded(session)
    assert guided.keep(seeded, _plan(seeded), 0, 1, [], [guided.Done(0, 1, 5)]) == 1
    torso = seeded.scalars(select(SessionTemplate).where(SessionTemplate.slug == "torso")).one()
    state = users.plan_state(seeded)
    assert state is not None
    state.next_template_id = torso.id
    seeded.flush()
    assert guided.keep(seeded, _plan(seeded), 1, 0, [], []) == guided.STALE
    assert seeded.scalars(select(SessionProgress)).one().sets  # Legs' sets are still kept


def test_a_day_logged_another_way_is_not_pending(session: Session) -> None:
    seeded = _seeded(session)
    plan = _plan(seeded)
    guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 5)])
    seeded.add(Workout(local_date=DAY, template_id=plan.template_id, status=WorkoutStatus.DONE))
    seeded.flush()
    assert guided.pending(seeded, DAY.replace(day=DAY.day + 1)) == []


# ------------------------------------------------------------- set times (ADR-0061)

NOW = datetime(2026, 10, 12, 16, 30, tzinfo=UTC)
AT = NOW - timedelta(minutes=20)  # a set's screen appeared


def _timed(item: int, set_no: int, value: int, start: datetime, seconds: int) -> guided.Done:
    return guided.Done(
        item, set_no, value, started_at=start, done_at=start + timedelta(seconds=seconds)
    )


def test_set_times_are_kept_in_utc_and_come_back_on_resume(session: Session) -> None:
    seeded = _seeded(session)
    plan = _plan(seeded)
    local = AT.astimezone(BERLIN)  # a phone sends its own offset
    assert guided.keep(seeded, plan, 0, 1, [], [_timed(0, 1, 5, local, 40)], now=NOW) == 1
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    (done,) = kept.sets
    assert (done.started_at, done.done_at) == (AT, AT + timedelta(seconds=40))
    assert done.started_at is not None
    assert done.started_at.tzinfo == UTC


def test_implausible_set_times_are_dropped_but_the_set_kept(session: Session) -> None:
    seeded = _seeded(session)
    plan = _plan(seeded)
    future = NOW + timedelta(minutes=5)
    sets = [
        _timed(0, 1, 5, future, 40),  # a phone clock running ahead
        guided.Done(0, 2, 6, started_at=AT),  # only one of the two
    ]
    assert guided.keep(seeded, plan, 0, 2, [], sets, now=NOW) == 1
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert [(d.set_no, d.left, d.started_at, d.done_at) for d in kept.sets] == [
        (1, 5, None, None),
        (2, 6, None, None),
    ]


def test_progress_kept_before_set_times_still_loads(session: Session) -> None:
    seeded = _seeded(session)
    plan = _plan(seeded)
    guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 5)], now=NOW)
    row = seeded.scalars(select(SessionProgress)).one()
    row.sets = [{"item": 0, "set_no": 1, "left": 5, "right": None}]  # as kept until ADR-0061
    seeded.flush()
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert kept.sets == (guided.Done(0, 1, 5),)


def test_saving_puts_each_sets_times_on_its_rows(session: Session) -> None:
    """Numbered as the log numbers them (a skipped set closes the gap), both sides of a
    one-sided set sharing the set's times."""
    seeded = _seeded(session)
    plan = _plan(seeded)
    side = next(i for i, item in enumerate(plan.items) if item.per_side)
    first, third, one_sided = AT, AT + timedelta(minutes=4), AT + timedelta(minutes=8)
    sets = [
        _timed(0, 1, 6, first, 30),
        _timed(0, 3, 4, third, 35),  # set 2 skipped: logged as set 2
        _timed(side, 1, 8, one_sided, 60),
    ]
    guided.keep(seeded, plan, 0, 3, [], sets, now=NOW)
    saved = guided.save(seeded, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    rows = seeded.get_one(Workout, saved.workout_id).sets
    jump = [r for r in rows if r.side == "both"]
    assert sorted((r.set_no, r.started_at, r.done_at) for r in jump) == [
        (1, first, first + timedelta(seconds=30)),
        (2, third, third + timedelta(seconds=35)),
    ]
    sides = [(r.side, r.started_at, r.done_at) for r in rows if r.side != "both"]
    end = one_sided + timedelta(seconds=60)
    assert sorted(sides) == [("left", one_sided, end), ("right", one_sided, end)]


def test_sets_without_times_save_without_them(session: Session) -> None:
    seeded = _seeded(session)
    guided.keep(seeded, _plan(seeded), 0, 1, [], [guided.Done(0, 1, 5)], now=NOW)
    saved = guided.save(seeded, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    (row,) = seeded.get_one(Workout, saved.workout_id).sets
    assert (row.started_at, row.done_at) == (None, None)
