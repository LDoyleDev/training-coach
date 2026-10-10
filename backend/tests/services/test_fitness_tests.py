from datetime import date, timedelta

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from training_coach.db.models import User
from training_coach.db.session import make_session_factory
from training_coach.domain.enums import Side
from training_coach.domain.fitness_tests import Result, TimeOfDay, Unit
from training_coach.services import fitness_tests
from training_coach.services.fitness_tests import Conditions, Saved
from training_coach.services.users import OWNER

TODAY = date(2026, 10, 10)
MORNING = Conditions(TimeOfDay.MORNING, fed=False, slept_well=True)
TOKEN = "a" * 20


def test_the_plan_has_the_product_specs_two_days_of_tests() -> None:
    tests = fitness_tests.tests()
    day_1 = [t.slug for t in tests if t.day == 1]
    assert day_1 == ["max-pull-ups", "max-push-ups", "max-dips", "dead-hang"]
    by_slug = {t.slug: t for t in tests}
    assert by_slug["bulgarian-split-squat"].per_side
    assert by_slug["single-leg-calf-raise"].per_side
    assert by_slug["run-12-min"].unit is Unit.METRES
    assert by_slug["toe-touch"].unit is Unit.CM
    assert len(tests) == 10


def test_a_test_day_is_saved_once_and_read_back(session: Session) -> None:
    results = [Result("max-pull-ups", Side.BOTH, 8), Result("dead-hang", Side.BOTH, 45)]
    saved = fitness_tests.save(session, TODAY, TODAY, 1, MORNING, results, TOKEN)
    assert isinstance(saved, Saved)
    assert not saved.already_saved
    again = fitness_tests.save(session, TODAY, TODAY, 1, MORNING, results, TOKEN)
    assert again == Saved(saved.id, already_saved=True)
    (day,) = fitness_tests.history(session)
    assert (day.on, day.day, day.conditions) == (TODAY, 1, MORNING)
    assert day.results == tuple(results)


def test_history_is_newest_first(session: Session) -> None:
    for offset, token in ((3, "b" * 20), (0, "c" * 20)):
        on = TODAY - timedelta(days=offset)
        result = [Result("dead-hang", Side.BOTH, 30)]
        assert isinstance(fitness_tests.save(session, on, TODAY, 1, MORNING, result, token), Saved)
    assert [d.on for d in fitness_tests.history(session)] == [TODAY, TODAY - timedelta(days=3)]


def test_what_cant_be_saved_says_why(session: Session) -> None:
    hang = [Result("dead-hang", Side.BOTH, 30)]
    future = fitness_tests.save(session, TODAY + timedelta(days=1), TODAY, 1, MORNING, hang, TOKEN)
    assert future == "that day hasn't happened yet"
    old = fitness_tests.save(session, TODAY - timedelta(days=15), TODAY, 1, MORNING, hang, TOKEN)
    assert old == "tests more than 14 days ago can't be added"
    assert fitness_tests.save(session, TODAY, TODAY, 2, MORNING, hang, TOKEN) == (
        "dead-hang isn't a day 2 test"
    )
    assert fitness_tests.history(session) == []


def test_a_save_racing_another_with_the_same_token_returns_the_saved_day(engine: Engine) -> None:
    """Both Saves miss the token lookup; the second loses on the unique token (review of #137)."""
    hang = [Result("dead-hang", Side.BOTH, 30)]
    sessions = make_session_factory(engine, user_id=OWNER)
    with sessions() as first, sessions() as second:
        assert fitness_tests._saved(second, TOKEN) is None  # the second has looked already
        saved = fitness_tests.save(first, TODAY, TODAY, 1, MORNING, hang, TOKEN)
        first.commit()
        raced = fitness_tests.save(second, TODAY, TODAY, 1, MORNING, hang, TOKEN)
    assert isinstance(saved, Saved)
    assert raced == Saved(saved.id, already_saved=True)


def test_another_persons_token_is_refused_without_showing_their_day(engine: Engine) -> None:
    """Tokens are unique across people; a clash with someone else's can't return their day."""
    hang = [Result("dead-hang", Side.BOTH, 30)]
    with make_session_factory(engine)() as shared:
        shared.add(User(id=2))
        shared.commit()
    with make_session_factory(engine, user_id=2)() as other:
        assert isinstance(fitness_tests.save(other, TODAY, TODAY, 1, MORNING, hang, TOKEN), Saved)
        other.commit()
    with make_session_factory(engine, user_id=OWNER)() as mine:
        clash = fitness_tests.save(mine, TODAY, TODAY, 1, MORNING, hang, TOKEN)
        assert clash == "that test day couldn't be saved; try again"
        assert fitness_tests.history(mine) == []
