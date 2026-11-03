"""Last set: as many good reps as you can (ADR-0084): locked for a person's first 8 weeks, only
on exercises the catalogue allows that count in reps, only the last set the day plans after the
trim, fixed with the length, and marked in the saved workout's plan."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import SessionTemplate, Workout
from training_coach.domain.enums import Place, WorkoutStatus
from training_coach.services import guided, last_set, user_settings, users, workout_log
from training_coach.services.seed import apply_seed, load_plan

BERLIN = ZoneInfo("Europe/Berlin")
DAY = date(2026, 10, 12)
EIGHT_WEEKS = DAY - timedelta(weeks=8)
TIBIALIS, CALF = 1, 3  # indexes in Legs: both failure_ok, counted in reps
AMRAP = {"tibialis-raise", "calf-raise"}


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _first_workout(session: Session, on: date) -> None:
    session.add(Workout(local_date=on, status=WorkoutStatus.DONE, place=Place.HOME))
    session.flush()


@pytest.fixture
def trained(plan: Session) -> Session:
    """Eight weeks since the first workout, with the option on."""
    _first_workout(plan, EIGHT_WEEKS)
    user_settings.update(plan, last_set_amrap=True)
    return plan


def _at(session: Session, slug: str) -> None:
    template = session.scalars(select(SessionTemplate).where(SessionTemplate.slug == slug)).one()
    state = users.plan_state(session)
    assert state is not None
    state.next_template_id = template.id
    session.flush()


def _today(session: Session) -> guided.Guided:
    found = guided.today(session, DAY, BERLIN)
    assert found is not None
    return found


def _choose(session: Session, minutes: int | None) -> guided.Guided:
    kept = guided.kept(session, DAY)
    seen = kept.revision if kept is not None else 0
    assert isinstance(guided.choose_length(session, _today(session), seen, minutes, ()), int)
    return _today(session)


def _marked(found: guided.Guided) -> dict[str, int]:
    """The exercises whose last set is as many as you can, and how many sets the day has."""
    return {i.slug: len(i.targets) for i in found.items if i.last_set_amrap}


def _save(session: Session) -> Workout:
    saved = guided.save(session, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    return session.get_one(Workout, saved.workout_id)


@pytest.mark.parametrize(
    ("first", "available"),
    [
        (None, False),
        (DAY, False),
        (EIGHT_WEEKS + timedelta(days=1), False),
        (EIGHT_WEEKS, True),
    ],
)
def test_locked_until_8_weeks_after_the_first_workout(
    plan: Session, first: date | None, available: bool
) -> None:
    if first is not None:
        _first_workout(plan, first)
    user_settings.update(plan, last_set_amrap=True)
    assert last_set.available(plan, DAY) is available
    found = _today(plan)
    assert found.length is not None
    assert found.length.last_set is (True if available else None)
    assert set(_marked(found)) == (AMRAP if available else set())


def test_a_skipped_or_rest_day_does_not_start_the_8_weeks(plan: Session) -> None:
    plan.add(Workout(local_date=EIGHT_WEEKS, status=WorkoutStatus.REST, place=Place.HOME))
    plan.flush()
    assert last_set.available(plan, DAY) is False


def test_off_by_default_and_nothing_marked(plan: Session) -> None:
    _first_workout(plan, EIGHT_WEEKS)
    assert user_settings.load(plan).last_set_amrap is False
    found = _today(plan)
    assert found.length is not None
    assert found.length.last_set is False
    assert _marked(found) == {}


def test_only_failure_ok_reps_exercises_and_their_last_planned_set(trained: Session) -> None:
    assert _marked(_today(trained)) == {"tibialis-raise": 3, "calf-raise": 4}
    # Third and fourth sets go at 40 minutes: the last set the day plans is the second.
    assert _marked(_choose(trained, 40)) == {"tibialis-raise": 2, "calf-raise": 2}


def test_an_exercise_the_trim_drops_has_no_last_set(trained: Session) -> None:
    found = _choose(trained, 20)  # tibialis and calf raises are dropped at 20 minutes
    assert found.length is not None
    assert found.length.last_set is True
    assert _marked(found) == {}


def test_a_recovery_session_never_has_one(trained: Session) -> None:
    _at(trained, "recovery")  # Prone Y-T-W is failure_ok, but the session has no length
    found = _today(trained)
    assert found.length is None
    assert _marked(found) == {}


def test_the_bots_work_list_follows_it(trained: Session) -> None:
    found = _today(trained)
    plan = guided.session_plan(trained, found.template_id, None)
    assert plan is not None
    shown, length = guided.at_length(trained, DAY, plan)
    assert length is not None
    assert {i.slug for i in shown.items if i.last_set_amrap} == AMRAP


def test_the_save_marks_the_last_set_in_the_plan(trained: Session) -> None:
    found = _choose(trained, 40)
    done = [guided.Done(TIBIALIS, 1, 20), guided.Done(TIBIALIS, 2, 31), guided.Done(0, 1, 6)]
    guided.keep(trained, found, 2, 3, [], done)
    workout = _save(trained)
    assert workout.planned is not None
    assert workout.planned["tibialis-raise"] == {"sets": 2, "failure_set": 2}
    assert workout.planned["calf-raise"] == {"sets": 2}  # its last set wasn't done
    assert workout.planned["jump-squat"] == {"sets": 2}
    # Its reps are kept as done: readiness and bests read them.
    assert max(s.value for s in workout.sets) == 31


def test_a_skipped_set_before_it_numbers_it_as_the_log_does(trained: Session) -> None:
    found = _choose(trained, 40)
    guided.keep(trained, found, 2, 1, [], [guided.Done(TIBIALIS, 2, 31)])
    workout = _save(trained)
    assert workout.planned is not None
    assert workout.planned["tibialis-raise"] == {"sets": 2, "failure_set": 1}  # logged as set 1


def test_an_earlier_set_is_never_marked(trained: Session) -> None:
    found = _today(trained)
    guided.keep(trained, found, 0, 1, [], [guided.Done(TIBIALIS, 2, 31)])
    workout = _save(trained)
    assert workout.planned is not None
    assert workout.planned["tibialis-raise"] == {"sets": 3}


def test_the_option_is_fixed_with_the_first_set(trained: Session) -> None:
    found = _today(trained)
    guided.keep(trained, found, 0, 1, [], [guided.Done(0, 1, 6)])
    user_settings.update(trained, last_set_amrap=False)  # turned off mid-session
    again = _today(trained)
    assert set(_marked(again)) == AMRAP
    kept = guided.kept(trained, DAY)
    assert kept is not None
    sets = [guided.Done(0, 1, 6), guided.Done(CALF, 1, 15), guided.Done(CALF, 4, 30)]
    guided.keep(trained, again, kept.revision, 3, [], sets)
    workout = _save(trained)
    assert workout.planned is not None
    assert workout.planned["calf-raise"] == {"sets": 4, "failure_set": 2}


def test_turned_on_after_the_first_set_waits_for_the_next_session(plan: Session) -> None:
    _first_workout(plan, EIGHT_WEEKS)
    found = _today(plan)
    guided.keep(plan, found, 0, 1, [], [guided.Done(CALF, 4, 30)])
    user_settings.update(plan, last_set_amrap=True)
    assert _marked(_today(plan)) == {}
    workout = _save(plan)
    assert workout.planned is not None
    assert workout.planned["calf-raise"] == {"sets": 4}


def test_the_next_target_of_a_failure_set_is_its_target_plus_the_step(trained: Session) -> None:
    """Tibialis raise, 15-25 (step 3), first time at the step: both sets aimed 15. Set 2 ran to
    25: it counts as 15 met, so it aims 18, not 25 (the top). Set 1 did 20: it aims 23."""
    found = _choose(trained, 40)
    done = [guided.Done(TIBIALIS, 1, 20), guided.Done(TIBIALIS, 2, 25)]
    guided.keep(trained, found, 2, 2, [], done)
    _save(trained)
    _at(trained, "legs")
    later = guided.today(trained, DAY + timedelta(days=2), BERLIN)
    assert later is not None
    tibialis = later.items[TIBIALIS]
    assert tibialis.slug == "tibialis-raise"
    assert tibialis.targets == (23, 18, 18)  # set 3, not planned that day, comes from set 2


def test_without_the_mark_the_big_set_sets_the_target(plan: Session) -> None:
    """The same day with the option off: set 2's 25 reps aim the top of the range."""
    _first_workout(plan, EIGHT_WEEKS)
    found = _choose(plan, 40)
    done = [guided.Done(TIBIALIS, 1, 20), guided.Done(TIBIALIS, 2, 25)]
    guided.keep(plan, found, 2, 2, [], done)
    _save(plan)
    _at(plan, "legs")
    later = guided.today(plan, DAY + timedelta(days=2), BERLIN)
    assert later is not None
    assert later.items[TIBIALIS].targets == (23, 25, 25)
