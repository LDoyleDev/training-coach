"""A release changing an exercise in someone's plan tells them (ADR-0087), once, and only them."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from tests.services.test_seed import MINI_PLAN
from training_coach.db.models import PlanNotice, SessionTemplate, User
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.services import plan_notices
from training_coach.services.seed import apply_seed, load_plan

NOW = datetime(2026, 11, 6, 12, tzinfo=UTC)
RENAMED_STEP = MINI_PLAN.replace(
    "levels = { Negatives = 4, Strict = 4, Weighted = 6 }",
    'levels = { Negatives = 4, "Very strict" = 4, Weighted = 6 }',
).replace(
    'ladder = ["Negatives", "Strict", "Weighted"]',
    'ladder = ["Negatives", "Very strict", "Weighted"]\nrenames = { "Strict" = "Very strict" }',
)
NEW_STEP = MINI_PLAN.replace(
    "levels = { Negatives = 4, Strict = 4, Weighted = 6 }",
    'levels = { Negatives = 4, Strict = 4, Weighted = 6, "Muscle-up" = 6 }',
).replace(
    'ladder = ["Negatives", "Strict", "Weighted"]',
    'ladder = ["Negatives", "Strict", "Weighted", "Muscle-up"]',
)
RENAMED_EXERCISE = MINI_PLAN.replace('name = "Pull-up"', 'name = "Chin over bar"')


def _texts(session: Session) -> list[str]:
    return [n.text for n in plan_notices.unread(session)]


@pytest.fixture
def started(session: Session) -> Session:
    apply_seed(session, load_plan(MINI_PLAN))
    session.commit()
    return session


@pytest.mark.parametrize(
    ("plan", "text"),
    [
        (RENAMED_STEP, 'Pull-up: "Strict" is now "Very strict".'),
        (NEW_STEP, 'Pull-up: a new level, "Muscle-up".'),
        (RENAMED_EXERCISE, "Pull-up is now called Chin over bar."),
    ],
    ids=["step-renamed", "step-added", "exercise-renamed"],
)
def test_a_change_to_an_exercise_in_my_plan_tells_me_once(
    started: Session, plan: str, text: str
) -> None:
    apply_seed(started, load_plan(plan))
    started.commit()
    assert _texts(started) == [text]
    apply_seed(started, load_plan(plan))  # the next start finds nothing new to say
    started.commit()
    assert _texts(started) == [text]


def test_a_new_plan_and_a_changed_cue_say_nothing(started: Session) -> None:
    assert _texts(started) == []
    cue = MINI_PLAN.replace(
        'ladder = ["Negatives", "Strict", "Weighted"]',
        'ladder = ["Negatives", "Strict", "Weighted"]\n[exercises.cues]\nStrict = "Chin over."',
    )
    apply_seed(started, load_plan(cue))
    started.commit()
    assert _texts(started) == []


def test_it_tells_only_those_whose_plan_has_it(engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
        shared.flush()
        apply_seed(shared, load_plan(MINI_PLAN))
    # The second person takes the pull-up's session out of their plan.
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        upper = theirs.scalars(select(SessionTemplate).where(SessionTemplate.slug == "upper")).one()
        upper.items.clear()
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan(RENAMED_EXERCISE))
        told = shared.scalars(select(PlanNotice.user_id), execution_options={ALL_USERS: True}).all()
    assert told == [1]


def test_got_it_is_for_my_own_notices(engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
        shared.flush()
        apply_seed(shared, load_plan(MINI_PLAN))
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan(RENAMED_EXERCISE))
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        (mine,) = [n.id for n in plan_notices.unread(theirs)]
    with session_scope(make_session_factory(engine, user_id=1)) as owner:
        plan_notices.mark_read(owner, [mine], NOW)  # someone else's id finds nothing
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        assert [n.id for n in plan_notices.unread(theirs)] == [mine]
        plan_notices.mark_read(theirs, [mine], NOW)
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        assert plan_notices.unread(theirs) == []


def test_untold_skips_those_told_or_seen(started: Session) -> None:
    apply_seed(started, load_plan(RENAMED_STEP))
    apply_seed(started, load_plan(RENAMED_STEP.replace('name = "Pull-up"', 'name = "Bar pull"')))
    started.commit()
    first, second = [n.id for n in plan_notices.untold(started)]
    plan_notices.mark_told(started, [first], NOW)
    plan_notices.mark_read(started, [second], NOW)
    started.commit()
    assert plan_notices.untold(started) == []
    assert [n.id for n in plan_notices.unread(started)] == [first]
