"""Minutes per session (ADR-0082, T2): the person's setting is the length of every trimmable
session when the day has no choice; a day's own choice, As planned included, overrides it."""

from datetime import date
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, SessionProgress, SessionTemplate, Workout
from training_coach.domain.trim import WarmUp
from training_coach.services import guided, home, user_settings, users, workout_log
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.today import session_plan

BERLIN = ZoneInfo("Europe/Berlin")
DAY = date(2026, 10, 12)
AS_PLANNED = (3, 3, 3, 4, 3, 3, 3, 3)  # the bundled home Legs day


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


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


def _length(found: guided.Guided) -> guided.Length:
    assert found.length is not None
    return found.length


def _choose(session: Session, minutes: int | None) -> guided.Guided:
    kept = guided.kept(session, DAY)
    revision = kept.revision if kept is not None else 0
    assert isinstance(guided.choose_length(session, _today(session), revision, minutes, ()), int)
    return _today(session)


def _sets(found: guided.Guided) -> tuple[int, ...]:
    return tuple(len(item.targets) for item in found.items)


def test_the_setting_is_stored_and_cleared_and_each_change_is_logged(session: Session) -> None:
    assert user_settings.load(session).session_minutes is None  # as planned for everyone
    assert user_settings.update(session, session_minutes=30).session_minutes == 30
    assert user_settings.update(session, nudges_enabled=False).session_minutes == 30  # kept
    assert user_settings.update(session, clear_session_minutes=True).session_minutes is None
    changes = [e.payload for e in session.scalars(select(Event).order_by(Event.id))]
    assert {"session_minutes": 30} in changes
    assert {"session_minutes": 0} in changes  # 0: back to as planned


def test_without_the_setting_a_session_runs_as_planned(plan: Session) -> None:
    length = _length(_today(plan))
    assert (length.minutes, length.from_setting) == (None, False)


def test_the_setting_applies_when_the_day_has_no_choice(plan: Session) -> None:
    user_settings.update(plan, session_minutes=30)
    found = _today(plan)
    length = _length(found)
    assert (length.minutes, length.from_setting, length.fixed) == (30, True, False)
    assert _sets(found) == (2,) * 8
    assert length.trimmed.warm_up is WarmUp.RAMP
    assert found.minutes <= 30
    assert length.planned == 49  # as planned stays on offer for the day
    assert guided.kept(plan, DAY) is None  # reading it writes nothing


def test_a_days_choice_overrides_the_setting(plan: Session) -> None:
    user_settings.update(plan, session_minutes=30)
    found = _choose(plan, 20)
    length = _length(found)
    assert (length.minutes, length.from_setting) == (20, False)


def test_choosing_as_planned_for_the_day_overrides_the_setting(plan: Session) -> None:
    user_settings.update(plan, session_minutes=20)
    found = _choose(plan, None)
    length = _length(found)
    assert (length.minutes, length.from_setting) == (None, False)
    assert _sets(found) == AS_PLANNED
    assert found.warm_up


def test_a_day_that_chose_the_settings_minutes_is_its_own_choice(plan: Session) -> None:
    user_settings.update(plan, session_minutes=30)
    _choose(plan, 30)
    user_settings.update(plan, session_minutes=20)
    assert (_length(_today(plan)).minutes, _length(_today(plan)).from_setting) == (30, False)


def test_a_new_setting_reaches_a_day_that_has_not_chosen_or_started(plan: Session) -> None:
    user_settings.update(plan, session_minutes=40)
    assert _length(_today(plan)).minutes == 40
    user_settings.update(plan, session_minutes=20)
    assert _length(_today(plan)).minutes == 20
    user_settings.update(plan, clear_session_minutes=True)
    assert _sets(_today(plan)) == AS_PLANNED


def test_a_recovery_session_runs_as_planned_whatever_the_setting(plan: Session) -> None:
    user_settings.update(plan, session_minutes=20)
    _at(plan, "recovery")
    assert _today(plan).length is None


def test_a_hiit_session_counts_its_rounds_and_is_offered_no_length(plan: Session) -> None:
    _at(plan, "hiit")
    found = _length(_today(plan))
    assert found.planned == 4  # 8 rounds of 30 s to start, not one ordinary set
    assert found.options == ()
    assert found.minutes is None


@pytest.mark.parametrize(
    ("planned", "offered"),
    [
        (49, (40, 30, 20)),
        (40, (30, 20)),
        (31, (30, 20)),
        (30, (20,)),
        (21, (20,)),
        (20, ()),
        (6, ()),
    ],
)
def test_only_lengths_shorter_than_the_session_are_offered(
    plan: Session, monkeypatch: pytest.MonkeyPatch, planned: int, offered: tuple[int, ...]
) -> None:
    _at(plan, "moderate-cardio")  # no warm-up, so the estimate is the whole session
    monkeypatch.setattr(guided, "_estimator", lambda *_: lambda sets, durations: float(planned))
    found = _length(_today(plan))
    assert (found.planned, found.options) == (planned, offered)


def test_a_setting_the_session_already_fits_leaves_it_as_planned(plan: Session) -> None:
    user_settings.update(plan, session_minutes=20)
    _at(plan, "hiit")
    found = _length(_today(plan))
    assert found.minutes is None
    assert not found.from_setting


def test_a_strength_session_that_fits_the_setting_keeps_its_warm_up(
    plan: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_settings.update(plan, session_minutes=30)
    monkeypatch.setattr(guided, "_estimator", lambda *_: lambda sets, durations: 20.0)
    found = _length(_today(plan))  # Legs, 25 minutes with its 5-minute warm-up
    assert found.planned == 25
    assert found.minutes is None
    assert found.trimmed.warm_up is WarmUp.FULL


def test_a_length_chosen_before_the_session_fitted_it_counts_as_planned(plan: Session) -> None:
    _at(plan, "hiit")
    assert isinstance(guided.keep(plan, _today(plan), 0, 0, [], []), int)
    row = plan.scalars(select(SessionProgress)).one()
    row.length = {"minutes": 20, "keep": []}
    plan.flush()
    assert _length(_today(plan)).minutes is None


def test_a_length_no_shorter_than_the_session_is_refused(plan: Session) -> None:
    _at(plan, "hiit")
    assert guided.choose_length(plan, _today(plan), 0, 20, ()) == guided.NOT_SHORTER
    assert guided.kept(plan, DAY) is None


def test_a_started_session_keeps_the_length_it_was_fixed_at(
    plan: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    found = _choose(plan, 40)
    first = found.order[0]
    done = guided.Done(first.item, first.set_no, first.target)
    kept = guided.kept(plan, DAY)
    assert kept is not None
    assert isinstance(guided.keep(plan, found, kept.revision, 1, [], [done]), int)
    monkeypatch.setattr(guided, "_estimator", lambda *_: lambda sets, durations: 10.0)
    assert _length(_today(plan)).minutes == 40


def test_a_conditioning_session_follows_the_setting(plan: Session) -> None:
    user_settings.update(plan, session_minutes=30)
    _at(plan, "moderate-cardio")
    found = _today(plan)
    assert _length(found).from_setting
    assert found.items[0].targets == (10,)
    assert found.minutes <= 30


def test_the_length_is_fixed_by_the_first_set_even_if_the_setting_moves(plan: Session) -> None:
    user_settings.update(plan, session_minutes=30)
    found = _today(plan)
    assert guided.keep(plan, found, 0, 1, [], [guided.Done(0, 1, 6)]) == 1
    user_settings.update(plan, session_minutes=20)
    again = _today(plan)
    length = _length(again)
    assert (length.minutes, length.fixed, length.from_setting) == (30, True, False)
    assert _sets(again) == _sets(found)
    assert guided.choose_length(plan, again, 1, 40, ()) == guided.STARTED
    saved = guided.save(plan, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    assert plan.get_one(Workout, saved.workout_id).minutes == 30


def test_a_setting_that_changed_nothing_saves_no_minutes(plan: Session) -> None:
    """The short HIIT session already fits 20 minutes: the day counts as done as planned."""
    user_settings.update(plan, session_minutes=20)
    _at(plan, "hiit")
    found = _today(plan)
    assert guided.keep(plan, found, 0, 1, [], [guided.Done(0, 1, 8)]) == 1
    saved = guided.save(plan, DAY, DAY, BERLIN)
    assert isinstance(saved, workout_log.Saved)
    assert plan.get_one(Workout, saved.workout_id).minutes is None


def test_home_shows_the_minutes_at_the_setting_and_no_usual(
    plan: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(home.session_times, "usual_minutes", lambda *_: 45)
    before = home.home(plan, DAY, BERLIN)
    as_planned = before.today_minutes
    assert before.today_usual_minutes == 45
    user_settings.update(plan, session_minutes=20)
    found = home.home(plan, DAY, BERLIN)
    assert found.today_minutes == _today(plan).minutes
    assert as_planned is not None
    assert found.today_minutes is not None
    assert found.today_minutes < as_planned
    assert found.today_usual_minutes is None  # "usually" is as planned


def test_the_bots_work_list_follows_the_setting(plan: Session) -> None:
    user_settings.update(plan, session_minutes=20)
    template = _today(plan).template_id
    shown = session_plan(plan, template, None, {})
    assert shown is not None
    cut, length = guided.at_length(plan, DAY, shown)
    assert length is not None
    assert length.from_setting
    assert sum(1 for item in cut.items if item.targets) == 3
