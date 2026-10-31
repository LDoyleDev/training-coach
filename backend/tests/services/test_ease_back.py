"""Ease back in after three weeks or more away (ADR-0084), against the bundled plan.

Legs is the first session; its first exercise, the jump squat, has the steps "Bodyweight, full
rest", "Pause at bottom, then jump" and "Holding 8 kg". It starts on the first."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import Event, Exercise, LadderStep, SetLog, Workout
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.load import LoadKit
from training_coach.services import blocks, ease_back, guided, progress, users
from training_coach.services.seed import apply_seed, load_plan

BERLIN = ZoneInfo("Europe/Berlin")
DAY = date(2026, 10, 12)
JUMP = "jump-squat"


@pytest.fixture
def seeded(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _jump(session: Session) -> Exercise:
    return session.scalars(select(Exercise).where(Exercise.slug == JUMP)).one()


def _steps(session: Session) -> list[LadderStep]:
    return list(_jump(session).ladder)


def _on_pause(session: Session) -> None:
    jump = _jump(session)
    assert progress.set_level(session, jump.id, jump.ladder[1].id) is not None


def _done(session: Session, days_before: int) -> None:
    jump = _jump(session)
    state = users.exercise_state(session, jump.id)
    assert state is not None
    workout = Workout(local_date=DAY - timedelta(days=days_before), status=WorkoutStatus.DONE)
    workout.sets = [
        SetLog(
            exercise_id=jump.id,
            ladder_step_id=state.ladder_step_id,
            set_no=1,
            side=Side.BOTH,
            value=6,
        )
    ]
    session.add(workout)
    session.flush()


def _plan(session: Session) -> guided.Guided:
    plan = guided.today(session, DAY, BERLIN)
    assert plan is not None
    return plan


def _offered(session: Session) -> list[tuple[str, str]]:
    found = ease_back.offered(session, _plan(session), guided.kept(session, DAY))
    return [(r.slug, r.step) for r in found]


def test_three_weeks_away_offers_one_step_down_today(seeded: Session) -> None:
    bottom, pause, _ = _steps(seeded)
    _on_pause(seeded)
    _done(seeded, 21)
    assert _offered(seeded) == [(JUMP, bottom.name)]
    # Only exercises done before come back: the rest of Legs was never done.
    revision = ease_back.answer(seeded, _plan(seeded), guided.kept(seeded, DAY), 0, ease=True)
    assert revision == 2  # started, then changed
    kept = guided.kept(seeded, DAY)
    assert kept is not None
    assert kept.steps == ((JUMP, bottom.id),)  # for today only
    state = users.exercise_state(seeded, _jump(seeded).id)
    assert state is not None
    assert state.ladder_step_id == pause.id  # the level stays
    assert _plan(seeded).items[0].step_id == bottom.id
    assert _offered(seeded) == []  # asked once
    events = seeded.scalars(select(Event.payload).where(Event.kind == ease_back.ANSWERED)).all()
    assert events == [{"exercises": [[_jump(seeded).id, "2026-09-21"]], "eased": True}]


def test_not_today_is_asked_once_per_return(seeded: Session) -> None:
    _on_pause(seeded)
    _done(seeded, 30)
    assert ease_back.answer(seeded, _plan(seeded), None, 0, ease=False) == 0
    assert guided.kept(seeded, DAY) is None  # nothing changed
    assert _offered(seeded) == []
    _done(seeded, 25)  # a later break is a new return
    assert _offered(seeded) == [(JUMP, _steps(seeded)[0].name)]


@pytest.mark.parametrize("days_before", [0, 20])
def test_under_three_weeks_is_no_return(seeded: Session, days_before: int) -> None:
    _on_pause(seeded)
    _done(seeded, days_before)
    assert _offered(seeded) == []
    assert ease_back.answer(seeded, _plan(seeded), None, 0, ease=True) == ease_back.NOTHING


def test_nothing_below_the_first_step(seeded: Session) -> None:
    _done(seeded, 40)
    assert _offered(seeded) == []


def test_a_loaded_step_lowers_the_weight_instead(
    seeded: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _on_pause(seeded)
    _done(seeded, 40)
    name = _steps(seeded)[1].name
    monkeypatch.setattr(blocks, "_load_kits", lambda: {(JUMP, name): LoadKit.BARBELL})
    assert _offered(seeded) == []


def test_not_once_the_session_has_started(seeded: Session) -> None:
    _on_pause(seeded)
    _done(seeded, 40)
    plan = _plan(seeded)
    assert guided.keep(seeded, plan, 0, 1, [], [guided.Done(0, 1, 6)]) == 1
    assert _offered(seeded) == []


def test_a_stale_browser_changes_nothing(seeded: Session) -> None:
    _on_pause(seeded)
    _done(seeded, 40)
    plan = _plan(seeded)
    guided.keep(seeded, plan, 0, 0, [], [])  # started elsewhere, nothing done yet
    found = ease_back.answer(seeded, plan, guided.kept(seeded, DAY), 0, ease=True)
    assert found == guided.STALE
