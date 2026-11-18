"""A light-start day's workout keeps the most each exercise aimed for, the bottom of its range,
so its targets replay as given (ADR-0094): done at the bottom is met, and the next targets grow
from it."""

from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from tests.services.test_easy_start import _sessions, day, member, people
from training_coach.db.models import Workout
from training_coach.domain.easy_start import Phase
from training_coach.services import easy_start, guided, workout_log
from training_coach.services.today import session_plan

__all__ = ["member", "people"]  # fixtures

BERLIN = ZoneInfo("Europe/Berlin")


def _save_at_the_bottom(session: Session, n: int, more: int = 0) -> tuple[guided.Guided, Workout]:
    """Today's session on day ``n``, every set done at its target (``more`` above it)."""
    plan = guided.today(session, day(n), BERLIN)
    assert plan is not None
    done = [guided.Done(s.item, s.set_no, s.target + more) for s in plan.order]
    assert isinstance(guided.keep(session, plan, 0, len(done), [], done), int)
    saved = guided.save(session, day(n), day(n), BERLIN)
    assert isinstance(saved, workout_log.Saved)
    return plan, session.get_one(Workout, saved.workout_id)


def test_a_light_day_keeps_the_bottom_each_exercise_aimed_for(member: Session) -> None:
    easy_start.turn(member, True, day(0))
    plan, workout = _save_at_the_bottom(member, 0)
    assert workout.planned is not None
    assert {s: p["aim"] for s, p in workout.planned.items()} == {
        i.slug: i.bottom for i in plan.items
    }


def test_done_at_the_bottom_is_met_after_a_higher_baseline(member: Session) -> None:
    """Uncapped, the light day reads as a miss against baseline + step and holds it there."""
    before, _ = _save_at_the_bottom(member, -3, more=4)  # before it went on: 4 over the bottom
    easy_start.turn(member, True, day(0))
    plan, _ = _save_at_the_bottom(member, 0)  # the next session in the queue
    trained = {i.slug for i in before.items if i.load is None}
    index, first = next((n, i) for n, i in enumerate(plan.items) if i.slug in trained)
    assert first.targets == (first.bottom,)  # capped today
    as_planned = session_plan(member, plan.template_id)  # no day: the targets as they stand
    assert as_planned is not None
    grown = as_planned.items[index].targets[0]
    assert first.bottom < grown < first.bottom + 4  # from the bottom, not held at the baseline's


def test_any_other_day_keeps_no_aims(member: Session) -> None:
    _, workout = _save_at_the_bottom(member, 0)
    assert workout.planned is not None
    assert all("aim" not in p for p in workout.planned.values())


def test_the_last_light_session_keeps_its_aims(member: Session) -> None:
    """A day's phase counts the days before it, so the save that ends the light start is still
    a light day."""
    easy_start.turn(member, True, day(0))
    _sessions(member, 0, 2, 4)
    _, workout = _save_at_the_bottom(member, 14)  # the fourth, on the 14 days' floor
    assert easy_start.current(member, day(15)).phase is Phase.LOWER
    assert workout.planned is not None
    assert all("aim" in p for p in workout.planned.values())
