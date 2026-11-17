"""The easy start on the day's plan (ADR-0094): one set of each at the bottom of its range and
timed items at most 10 minutes in the light start, one set fewer of each in one set lower, before
exercises per session and the minutes trim it (ADR-0082 addendum). The map shows the plan as it
is; Move up waits in the light start. Nothing changes for the owner."""

from collections.abc import Iterator
from datetime import date
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.services.test_easy_start import _sessions, _to_lower, day, member, people
from training_coach.db.models import SessionTemplate, SetLog, UserSettings, Workout
from training_coach.db.session import make_session_factory
from training_coach.domain.easy_start import Phase
from training_coach.domain.enums import Place, Side, WorkoutStatus
from training_coach.domain.progression import Progress
from training_coach.services import (
    coverage,
    easy_start,
    guided,
    home,
    progress,
    review,
    user_settings,
    users,
)
from training_coach.services import today as today_service
from training_coach.services.today import SessionPlan

__all__ = ["member", "people"]  # fixtures

BERLIN = ZoneInfo("Europe/Berlin")


@pytest.fixture(autouse=True)
def at_the_top(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every set aims for the top of its range, so a cap at the bottom shows."""
    monkeypatch.setattr(today_service, "targets", lambda item, *_: (item.rep_max,) * item.sets)


@pytest.fixture
def owner(people: Engine) -> Iterator[Session]:
    with make_session_factory(people, user_id=users.OWNER)() as mine:
        yield mine


def _forced(owner: Session) -> None:
    """The owner is never offered it (Decided 13): set by hand here only for the sessions a
    member's starter doesn't have (a run, a recovery session), as a member's row would be."""
    row = users.settings_row(owner) or UserSettings()
    row.easy_start, row.easy_start_from = True, day(0)
    owner.add(row)
    owner.flush()


def _today(session: Session, on: date) -> guided.Guided:
    found = guided.today(session, on, BERLIN)
    assert found is not None
    return found


def _sets(items: tuple[today_service.ItemPlan, ...]) -> tuple[int, ...]:
    return tuple(len(i.targets) for i in items)


def _as_planned(session: Session, template_id: int) -> SessionPlan:
    """The session with no day: the plan as it is, as Plan and the map read it."""
    found = today_service.session_plan(session, template_id)
    assert found is not None
    assert found.easy is Phase.OFF
    return found


def _bottoms(session: Session, template_id: int) -> list[int]:
    template = session.get(SessionTemplate, template_id)
    assert template is not None
    return [i.rep_min for i in template.version(Place.HOME)]


def _shown(session: Session, slug: str, on: date) -> tuple[SessionPlan, guided.Length | None]:
    """A session as the bot shows it on ``on``."""
    template_id = session.scalars(
        select(SessionTemplate.id).where(SessionTemplate.slug == slug)
    ).one()
    plan = today_service.session_plan(session, template_id, on=on)
    assert plan is not None
    return guided.at_length(session, on, plan)


def test_the_owner_runs_as_planned(owner: Session) -> None:
    assert easy_start.turn(owner, True, day(0)) == easy_start.OWNER
    found = _today(owner, day(0))
    planned = _as_planned(owner, found.template_id)
    assert found.items == planned.items


def test_waiting_is_the_light_start_one_set_of_each_at_the_bottom(member: Session) -> None:
    easy_start.turn(member, True, day(0))
    found = _today(member, day(0))
    planned = _as_planned(member, found.template_id)
    assert _sets(found.items) == (1,) * len(planned.items)  # every exercise stays (Decided 3)
    bottoms = _bottoms(member, found.template_id)
    assert [i.targets for i in found.items] == [(b,) for b in bottoms]
    assert any(i.targets[0] > b for i, b in zip(planned.items, bottoms, strict=True))
    length = found.length
    assert length is not None
    assert length.trimmed.dropped == ()
    assert length.planned == found.minutes  # as planned is the light day


def test_a_light_day_keeps_its_weights(member: Session) -> None:
    easy_start.turn(member, True, day(0))
    _sessions(member, 0, 2)
    assert easy_start.current(member, day(8)).phase is Phase.LIGHT
    found = _today(member, day(8))
    planned = _as_planned(member, found.template_id)
    assert _sets(found.items) == (1,) * len(planned.items)
    for eased, as_planned in zip(found.items, planned.items, strict=True):
        assert (eased.load and eased.load.kg) == (as_planned.load and as_planned.load.kg[:1])


def test_one_set_lower_is_one_set_fewer_of_each_at_its_usual_targets(member: Session) -> None:
    _to_lower(member)
    found = _today(member, day(14))
    planned = _as_planned(member, found.template_id)
    assert _sets(found.items) == tuple(max(n - 1, 1) for n in _sets(planned.items))
    assert [i.targets[0] for i in found.items] == [i.targets[0] for i in planned.items]


def test_exercises_per_session_and_the_minutes_trim_on_top(member: Session) -> None:
    _to_lower(member)
    user_settings.update(member, session_exercises=4)
    found = _today(member, day(14))
    planned = _as_planned(member, found.template_id)
    lower = [max(n - 1, 1) for n in _sets(planned.items)]
    assert sum(n > 0 for n in _sets(found.items)) == 4
    assert all(n in (0, m) for n, m in zip(_sets(found.items), lower, strict=True))


def test_done_is_as_planned(member: Session) -> None:
    _to_lower(member)
    _sessions(member, *range(14, 30, 2))
    assert easy_start.current(member, day(45)).phase is Phase.DONE
    found = _today(member, day(45))
    assert found.items == _as_planned(member, found.template_id).items


def test_a_timed_item_is_at_most_10_minutes_in_the_light_start(owner: Session) -> None:
    _forced(owner)
    shown, length = _shown(owner, "moderate-cardio", day(0))
    assert length is not None
    assert shown.items[0].targets == (10,)
    assert _sets(shown.items) == (1,) * len(shown.items)
    _sessions(owner, 0, 2, 4, 6)
    shown, _ = _shown(owner, "moderate-cardio", day(14))  # one set lower
    assert shown.items[0].targets == (40,)  # the run as planned, its one set staying one


def test_a_recovery_session_is_unchanged(owner: Session) -> None:
    _forced(owner)
    shown, length = _shown(owner, "recovery", day(0))
    assert length is None
    assert shown.easy is Phase.OFF
    assert shown.items == _as_planned(owner, shown.template_id).items


def test_a_started_session_keeps_its_sets(member: Session) -> None:
    found = _today(member, day(0))
    first = found.order[0]
    done = guided.Done(first.item, first.set_no, first.target)
    assert isinstance(guided.keep(member, found, 0, 1, [], [done]), int)
    easy_start.turn(member, True, day(0))  # on during the session: it runs as it started
    assert _sets(_today(member, day(0)).items) == _sets(found.items)


def test_a_walk_logged_through_the_bot_doesnt_start_it(member: Session) -> None:
    easy_start.turn(member, True, day(0))
    member.add(Workout(local_date=day(0), template_id=None, status=WorkoutStatus.DONE))
    member.flush()
    assert easy_start.current(member, day(1)).phase is Phase.WAITING
    assert set(_sets(_today(member, day(1)).items)) == {1}


def test_the_map_shows_the_plan_as_it_is(member: Session) -> None:
    """Decided 11: ``coverage`` previews through ``guided.fitted``, which the easy start skips."""
    before = coverage.plan_coverage(member)
    easy_start.turn(member, True, day(0))
    _sessions(member, 0)
    assert easy_start.current(member, day(1)).phase is Phase.LIGHT
    assert coverage.plan_coverage(member) == before


# ---------------------------------------------------------------- Move up waits (Decided 10)


def _top(session: Session, on: date) -> int:
    """A workout of the person's first session with every set of its first exercise at the top."""
    template = session.scalars(select(SessionTemplate).order_by(SessionTemplate.position)).first()
    assert template is not None
    item = template.items[0]
    state = users.exercise_state(session, item.exercise_id)
    assert state is not None
    workout = Workout(local_date=on, template_id=template.id, status=WorkoutStatus.DONE)
    workout.sets = [
        SetLog(
            exercise_id=item.exercise_id,
            ladder_step_id=state.ladder_step_id,
            set_no=n,
            side=Side.BOTH,
            value=item.rep_max,
        )
        for n in range(1, item.sets + 1)
    ]
    session.add(workout)
    session.flush()
    return workout.id


@pytest.fixture
def ready(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every exercise trained meets the ready rule."""
    monkeypatch.setattr(progress, "_status", lambda *_: Progress.READY)


@pytest.mark.usefixtures("ready")
def test_move_up_waits_in_the_light_start_and_comes_back_in_one_set_lower(
    member: Session,
) -> None:
    easy_start.turn(member, True, day(0))
    _top(member, day(0))
    assert progress.holding(member, day(0))
    (light,) = progress.feedback(member, _top(member, day(2)))
    assert light.status is Progress.HOLD
    assert home.home(member, day(3), BERLIN).progress.ready == []
    assert review.weekly(member, day(3), BERLIN).ready == []
    standings = progress.overview(member)
    assert any(s.status is Progress.READY for s in standings)  # still judged
    assert all(s.status is not Progress.READY for s in progress.held(standings))
    _sessions(member, 4, 6)
    assert not progress.holding(member, day(14))
    (lower,) = progress.feedback(member, _top(member, day(14)))
    assert lower.status is Progress.READY  # offered again from one set lower
    assert home.home(member, day(15), BERLIN).progress.ready != []


@pytest.mark.usefixtures("ready")
def test_move_up_is_offered_with_the_easy_start_off(member: Session) -> None:
    assert not progress.holding(member, day(0))
    (item,) = progress.feedback(member, _top(member, day(0)))
    assert item.status is Progress.READY
    assert review.weekly(member, day(1), BERLIN).ready != []
