"""The guided session's view of today (#117), against the bundled plan."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests import factories
from training_coach.db.models import Exercise, SessionProgress, SessionTemplate, SetLog, Workout
from training_coach.db.session import make_session_factory
from training_coach.domain.enums import Place, Places, Side, WorkoutStatus
from training_coach.domain.kit import Item
from training_coach.domain.load import Load, LoadKit
from training_coach.domain.muscles import Kit
from training_coach.domain.progression import Progress
from training_coach.services import (
    blocks,
    equipment,
    guided,
    progress,
    queue_actions,
    today,
    user_settings,
    users,
    workout_log,
)
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
    assert plan.rest_seconds == 60  # after a pair, for pages from before ADR-0065
    assert 40 <= plan.minutes <= 90  # warm-up plus 25 sets, some per side


def test_a_pair_switches_inside_and_rests_after_the_round(session: Session) -> None:
    """Jump squat + tibialis raise share no prime mover: 15 s to move, 60 s after (ADR-0065)."""
    plan = guided.today(_seeded(session), DAY, BERLIN)
    assert plan is not None
    first, second = plan.order[:2]
    assert (first.rest.seconds, first.rest.switch) == (15, True)
    assert (second.rest.seconds, second.rest.switch) == (60, False)
    assert plan.order[-1].rest.seconds == 0  # the session is over


def test_a_pair_sharing_a_prime_mover_rests_longer(session: Session) -> None:
    """Pistol squat + single-leg RDL both count fully for the glutes: 90 s after the round."""
    plan = guided.today(_seeded(session), DAY, BERLIN)
    assert plan is not None
    pistol = next(i for i, item in enumerate(plan.items) if item.slug == "pistol-squat")
    rounds = [s for s in plan.order if s.item == pistol + 1 and s is not plan.order[-1]]
    assert rounds
    assert all(s.rest.seconds == 90 for s in rounds)


def test_the_estimate_counts_the_rests_the_session_runs(session: Session) -> None:
    plan = guided.today(_seeded(session), DAY, BERLIN)
    assert plan is not None
    rested = sum(s.rest.seconds for s in plan.order)
    assert rested < 60 * len(plan.order)  # shorter than a minute after every set


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
    assert paired == ["dead-hang", "neck-extension"]  # one set each since "Rear delts + carries"


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


# ---------------------------------------------------------------- load (ADR-0072)


@pytest.fixture
def loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    """The jump squat, Legs' first exercise, as if its step took dumbbells."""
    monkeypatch.setattr(
        blocks, "_load_kits", lambda: factories.loads("jump-squat", LoadKit.DUMBBELLS)
    )


@pytest.mark.usefixtures("loaded")
def test_a_loaded_step_starts_at_the_kits_first_weight_then_carries_over(
    session: Session,
) -> None:
    seeded = _seeded(session)
    plan = _plan(seeded)
    assert plan.items[0].load == Load(LoadKit.DUMBBELLS, 2.0, (8.0, 8.0, 8.0), carried=False)
    assert all(item.load is None for item in plan.items[1:])
    done = [guided.Done(0, 1, 8, load_kg=12.0), guided.Done(0, 2, 7, load_kg=14.0)]
    assert guided.keep(seeded, plan, 0, 2, [], done) == 1
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert [d.load_kg for d in kept.sets] == [12.0, 14.0]
    saved = guided.save(seeded, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    rows = seeded.get_one(Workout, saved.workout_id).sets
    assert sorted((r.set_no, r.load_kg) for r in rows) == [(1, 12.0), (2, 14.0)]
    again = today.session_plan(seeded, plan.template_id)
    assert again is not None
    load = again.items[0].load
    assert load is not None
    assert (load.kg, load.carried) == ((12.0, 14.0, 14.0), True)


@pytest.mark.usefixtures("loaded")
@pytest.mark.parametrize(
    ("done", "problem"),
    [
        (guided.Done(1, 1, 8, load_kg=10.0), "isn't done with a weight"),
        (guided.Done(0, 1, 8, load_kg=0.0), "more than 0 and at most 500 kg"),
        (guided.Done(0, 1, 8, load_kg=600.0), "more than 0 and at most 500 kg"),
    ],
    ids=["unloaded-step", "nothing", "too-heavy"],
)
def test_a_weight_only_goes_with_a_loaded_step_and_in_range(
    session: Session, done: guided.Done, problem: str
) -> None:
    seeded = _seeded(session)
    result = guided.keep(seeded, _plan(seeded), 0, 1, [], [done])
    assert isinstance(result, str)
    assert problem in result


def test_progress_kept_before_loads_still_loads(session: Session) -> None:
    seeded = _seeded(session)
    guided.keep(seeded, _plan(seeded), 0, 1, [], [guided.Done(0, 1, 5)])
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert kept.sets[0].load_kg is None


def _logged(session: Session, day: date, reps: int, kg: float | tuple[float, ...]) -> int:
    """Three sets of the jump squat at its current step, as a done workout on ``day``: at one
    weight, or one per set."""
    weights = kg if isinstance(kg, tuple) else (kg,) * 3
    jump = session.scalars(select(Exercise).where(Exercise.slug == "jump-squat")).one()
    state = users.exercise_state(session, jump.id)
    assert state is not None
    workout = Workout(local_date=day, status=WorkoutStatus.DONE)
    workout.sets.extend(
        SetLog(
            exercise_id=jump.id,
            ladder_step_id=state.ladder_step_id,
            set_no=n,
            value=reps,
            load_kg=weights[n - 1],
        )
        for n in (1, 2, 3)
    )
    session.add(workout)
    session.flush()
    return workout.id


@pytest.mark.usefixtures("loaded")
def test_every_set_at_the_top_suggests_the_next_weight_which_starts_afresh(
    session: Session,
) -> None:
    """Double progression (ADR-0072): the suggestion is offered, never applied; a heavier
    weight's targets grow from its own sessions."""
    seeded = _seeded(session)
    template = _plan(seeded).template_id
    _logged(seeded, DAY - timedelta(days=7), 30, 12.0)
    first = today.session_plan(seeded, template)
    assert first is not None
    load = first.items[0].load
    assert load is not None
    assert load.kg == (12.0, 12.0, 12.0)  # still last time's weight until the person taps
    assert load.suggested is not None
    assert load.suggested.kg == 14.0
    bottom = load.suggested.targets[0]
    assert load.suggested.targets == (bottom,) * 3
    assert first.items[0].targets[0] > bottom  # at the top of the range at 12 kg

    _logged(seeded, DAY - timedelta(days=3), bottom, 14.0)
    second = today.session_plan(seeded, template)
    assert second is not None
    heavier = second.items[0]
    assert heavier.load is not None
    assert (heavier.load.kg, heavier.load.suggested) == ((14.0,) * 3, None)
    assert heavier.targets[0] < first.items[0].targets[0]  # from 14 kg's own session


@pytest.mark.usefixtures("loaded")
def test_a_strength_block_keeps_a_loaded_step_without_the_tempo_cue(session: Session) -> None:
    seeded = _seeded(session)
    jump = seeded.scalars(select(Exercise).where(Exercise.slug == "jump-squat")).one()
    step, at_top = blocks.step_for(seeded, jump, strength=True)
    state = users.exercise_state(seeded, jump.id)
    assert state is not None
    assert (step.id, at_top) == (state.ladder_step_id, False)


@pytest.mark.usefixtures("loaded")
def test_bests_count_at_the_same_weight_only(session: Session) -> None:
    """More reps at a lighter weight is no record; more at the same weight is."""
    seeded = _seeded(session)
    _logged(seeded, DAY - timedelta(days=7), 10, 20.0)
    lighter = _logged(seeded, DAY - timedelta(days=5), 12, 16.0)
    (found,) = progress.feedback(seeded, lighter)
    assert (found.bests.best_set, found.status) == (None, Progress.HOLD)
    same = _logged(seeded, DAY - timedelta(days=3), 11, 20.0)
    (found,) = progress.feedback(seeded, same)
    assert found.bests.best_set == 11


@pytest.mark.usefixtures("loaded")
@pytest.mark.parametrize(
    ("weights", "suggested"),
    [((14.0, 12.0, 12.0), None), ((14.0, 14.0, 14.0), 16.0)],
    ids=["pyramid", "all-at-the-weight"],
)
def test_the_next_weight_waits_until_every_set_was_at_the_weight(
    session: Session, weights: tuple[float, ...], suggested: float | None
) -> None:
    """One set at 14 kg and the rest at 12 kg is not a session at 14 kg (review of #382): the
    next weight is suggested only when every set was done at it, all at the top."""
    seeded = _seeded(session)
    _logged(seeded, DAY - timedelta(days=7), 30, weights)
    plan = today.session_plan(seeded, _plan(seeded).template_id)
    assert plan is not None
    load = plan.items[0].load
    assert load is not None
    assert (load.suggested.kg if load.suggested else None) == suggested


# ------------------------------------------------------------ home or gym (ADR-0071)


def _at_both(session: Session, place: Place = Place.HOME) -> Session:
    seeded = _seeded(session)
    user_settings.update(seeded, places=Places.BOTH, place=place)
    return seeded


def test_someone_at_home_only_gets_the_home_version_and_no_switch(session: Session) -> None:
    plan = guided.today(_seeded(session), DAY, BERLIN)
    assert plan is not None
    assert (plan.place, plan.switch) == (Place.HOME, False)
    assert "back-squat" not in {i.slug for i in plan.items}


def test_at_both_the_last_place_chosen_gives_its_version_and_a_switch(session: Session) -> None:
    plan = guided.today(_at_both(session, Place.GYM), DAY, BERLIN)
    assert plan is not None
    assert (plan.place, plan.switch) == (Place.GYM, True)
    squat = next(i for i in plan.items if i.slug == "back-squat")
    assert squat.load is not None
    assert squat.load.kit is LoadKit.BARBELL
    assert [plan.items[s.item].slug for s in plan.order[:2]] == ["jump-squat", "tibialis-raise"]


def test_someone_at_the_gym_only_gets_the_gym_version_without_a_switch(session: Session) -> None:
    seeded = _seeded(session)
    user_settings.update(seeded, places=Places.GYM)
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    assert (plan.place, plan.switch) == (Place.GYM, False)
    assert "seated-leg-curl" in {i.slug for i in plan.items}


def test_a_session_with_one_version_has_no_switch(session: Session) -> None:
    seeded = _at_both(session, Place.GYM)
    state = users.plan_state(seeded)
    assert state is not None
    state.next_template_id = seeded.scalars(
        select(SessionTemplate.id).where(SessionTemplate.slug == "recovery")
    ).one()
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    assert plan.slug == "recovery"
    assert (plan.place, plan.switch) == (Place.HOME, False)  # its one version is the home one
    assert "prone-ytw" in {i.slug for i in plan.items}


def test_switching_before_any_set_changes_the_exercises_and_the_next_default(
    session: Session,
) -> None:
    seeded = _at_both(session)
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    guided.keep(seeded, plan, 0, 0, [1], [])  # a pair swapped, no set yet
    assert guided.switch(seeded, plan, Place.GYM, confirm=False) is None
    assert guided.kept(seeded, DAY) is None  # the swap belonged to the home version
    assert user_settings.load(seeded).place is Place.GYM
    gym = guided.today(seeded, DAY, BERLIN)
    assert gym is not None
    assert gym.place is Place.GYM
    assert guided.switch(seeded, gym, Place.GYM, confirm=False) is None  # already there


def test_switching_with_sets_kept_asks_first_then_drops_them(session: Session) -> None:
    seeded = _at_both(session)
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    guided.keep(seeded, plan, 0, 2, [], [guided.Done(0, 1, 6), guided.Done(1, 1, 18)])
    assert guided.switch(seeded, plan, Place.GYM, confirm=False) == 2
    assert user_settings.load(seeded).place is Place.HOME  # nothing changed
    assert guided.kept(seeded, DAY) is not None
    assert guided.switch(seeded, plan, Place.GYM, confirm=True) is None
    assert guided.kept(seeded, DAY) is None
    assert user_settings.load(seeded).place is Place.GYM


def test_a_gym_session_is_saved_at_the_gym_with_its_weights(session: Session) -> None:
    seeded = _at_both(session, Place.GYM)
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    squat = next(n for n, i in enumerate(plan.items) if i.slug == "back-squat")
    assert guided.keep(seeded, plan, 0, 1, [], [guided.Done(squat, 1, 8, load_kg=60)]) == 1
    saved = guided.save(seeded, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    workout = seeded.get_one(Workout, saved.workout_id)
    assert workout.place == "gym"
    assert [(s.value, s.load_kg) for s in workout.sets] == [(8, 60.0)]


def test_a_typed_log_is_filed_at_the_days_place(session: Session) -> None:
    seeded = _at_both(session, Place.GYM)
    draft = workout_log.draft(seeded, "back squat 8 8 8 at 60", DAY, BERLIN)
    assert draft.problems == ()
    saved = workout_log.save(seeded, draft, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    assert seeded.get_one(Workout, saved.workout_id).place == "gym"


def test_a_day_left_unsaved_at_home_saves_at_home_after_a_switch_to_the_gym(
    session: Session,
) -> None:
    seeded = _at_both(session)
    home = guided.today(seeded, DAY, BERLIN)
    assert home is not None
    assert home.place is Place.HOME
    sets = [guided.Done(0, 1, 6), guided.Done(1, 1, 18)]
    assert guided.keep(seeded, home, 0, 2, [], sets) == 1  # left unsaved
    later = DAY + timedelta(days=1)
    tomorrow = guided.today(seeded, later, BERLIN)
    assert tomorrow is not None
    assert guided.switch(seeded, tomorrow, Place.GYM, confirm=False) is None  # the next day
    saved = guided.save(seeded, DAY, later, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    workout = seeded.get_one(Workout, saved.workout_id)
    assert workout.place == "home"
    slugs = dict(seeded.execute(select(Exercise.id, Exercise.slug)).all())
    assert {slugs[s.exercise_id] for s in workout.sets} == {i.slug for i in home.items[:2]}


def _gym_only_at(session: Session, slug: str) -> Session:
    """Someone who trains only at a gym, with ``slug`` next in the queue."""
    seeded = _seeded(session)
    user_settings.update(seeded, places=Places.GYM)
    state = users.plan_state(seeded)
    assert state is not None
    state.next_template_id = seeded.scalars(
        select(SessionTemplate.id).where(SessionTemplate.slug == slug)
    ).one()
    seeded.flush()
    return seeded


def test_at_the_gym_only_a_session_without_a_gym_version_is_saved_at_home(
    session: Session,
) -> None:
    """Review of #406: Recovery has no gym version, so at the gym it is its home exercises, and
    the plan, the guided save and the saved screen's kit locks all say home, not gym."""
    seeded = _gym_only_at(session, "recovery")
    equipment.save(seeded, [Item(Kit.KETTLEBELL, kg=8)], datetime(2026, 10, 1, 9, tzinfo=UTC))
    plan = guided.today(seeded, DAY, BERLIN)
    assert plan is not None
    assert (plan.slug, plan.place, plan.switch) == ("recovery", Place.HOME, False)
    carry = next(n for n, i in enumerate(plan.items) if i.slug == "suitcase-carry")
    exercise = seeded.scalars(select(Exercise).where(Exercise.slug == "suitcase-carry")).one()
    state = users.exercise_state(seeded, exercise.id)
    assert state is not None
    before = Workout(  # the top of the range once already, at 8 kg
        local_date=DAY - timedelta(days=3), template_id=plan.template_id, status="done"
    )
    before.sets.extend(
        SetLog(
            exercise_id=exercise.id,
            ladder_step_id=state.ladder_step_id,
            set_no=n,
            side=side,
            value=45,
        )
        for n in (1, 2)
        for side in (Side.LEFT, Side.RIGHT)
    )
    seeded.add(before)
    seeded.flush()
    sets = [guided.Done(carry, 1, 45, 45), guided.Done(carry, 2, 45, 45)]
    assert guided.keep(seeded, plan, 0, 2, [], sets) == 1
    saved = guided.save(seeded, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    assert seeded.get_one(Workout, saved.workout_id).place == "home"
    found = next(f for f in progress.feedback(seeded, saved.workout_id, BERLIN))
    # Only an 8 kg bell at home: the 16 kg step is locked, as it would not be at a gym
    assert (found.status, found.next_step) == (Progress.TOP_OF_LADDER, None)
    assert found.unlock == "a 16 kg kettlebell unlocks 16 kg"


def test_at_the_gym_only_a_typed_log_of_a_one_version_session_is_filed_at_home(
    session: Session,
) -> None:
    seeded = _gym_only_at(session, "recovery")
    draft = workout_log.draft(seeded, "dead hang 45", DAY, BERLIN)
    assert (draft.problems, draft.session_name) == ((), "Recovery + posture")
    saved = workout_log.save(seeded, draft, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    assert seeded.get_one(Workout, saved.workout_id).place == "home"


def test_at_the_gym_only_a_typed_log_of_a_gym_session_is_filed_at_the_gym(
    session: Session,
) -> None:
    seeded = _gym_only_at(session, "legs")
    draft = workout_log.draft(seeded, "back squat 8 8 8 at 60", DAY, BERLIN)
    assert draft.problems == ()
    saved = workout_log.save(seeded, draft, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    assert seeded.get_one(Workout, saved.workout_id).place == "gym"
