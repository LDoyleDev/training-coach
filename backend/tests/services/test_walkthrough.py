"""The walk-through's answers (ADR-0092): kept only with consent, one row a person, replaced by a
re-run, deleted by a withdrawal and with the person; the plan and settings stay."""

from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError

from training_coach.db.models import PlanState, User, UserSettings, WalkthroughAnswers
from training_coach.db.session import ALL_USERS, make_session_factory, session_scope
from training_coach.domain.consent import VERSIONS, Category
from training_coach.domain.walkthrough import AgeBand, Answers, CanDo, Effort, HowLong, Often
from training_coach.services import consent, erase, left_list, users, walkthrough

MEMBER = 2
NOW = datetime(2026, 11, 9, 9, tzinfo=UTC)
ANSWERS = Answers(
    age_band=AgeBand.UNDER_75,
    often=Often.ONE_TWO,
    effort=Effort.TALK,
    how_long=HowLong.TEN_TO_30,
    chair=True,
    stairs=True,
    walk=True,
    floor=False,
    weekdays=(4, 0, 2),
    placement={"push-up": ((11, CanDo.YES), (12, CanDo.NO))},
)


@pytest.fixture
def member(engine: Engine) -> Engine:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=MEMBER, role=users.MEMBER))
    return engine


def _kept(engine: Engine, user: int) -> int:
    with session_scope(make_session_factory(engine)) as shared:
        query = select(func.count()).select_from(WalkthroughAnswers)
        query = query.where(WalkthroughAnswers.user_id == user)
        return shared.scalar(query, execution_options={ALL_USERS: True}) or 0


def test_without_consent_nothing_is_kept(member: Engine) -> None:
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        assert walkthrough.keep(theirs, MEMBER, ANSWERS, NOW) is False
        assert walkthrough.kept(theirs) is None
    assert _kept(member, MEMBER) == 0


def test_with_consent_the_answers_are_kept_at_the_wording_version(member: Engine) -> None:
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        consent.give(theirs, Category.WALKTHROUGH, NOW)
        assert walkthrough.keep(theirs, MEMBER, ANSWERS, NOW)
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        assert walkthrough.kept(theirs) == replace(ANSWERS, weekdays=(0, 2, 4))
        row = theirs.scalars(select(WalkthroughAnswers)).one()
        assert row.version == VERSIONS[Category.WALKTHROUGH] == 2
        assert row.answered_at == NOW


def test_a_re_run_replaces_the_answers(member: Engine) -> None:
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        consent.give(theirs, Category.WALKTHROUGH, NOW)
        walkthrough.keep(theirs, MEMBER, ANSWERS, NOW)
        walkthrough.keep(theirs, MEMBER, Answers(weekdays=(5,)), NOW)
        assert walkthrough.kept(theirs) == Answers(weekdays=(5,))  # skipped ones are empty
    assert _kept(member, MEMBER) == 1


def test_the_owner_is_never_asked(member: Engine) -> None:
    with session_scope(make_session_factory(member, user_id=users.OWNER)) as mine:
        assert walkthrough.keep(mine, users.OWNER, ANSWERS, NOW)
    assert _kept(member, users.OWNER) == 1


def test_withdrawing_deletes_the_answers_only_and_only_theirs(member: Engine) -> None:
    with session_scope(make_session_factory(member, user_id=users.OWNER)) as mine:
        walkthrough.keep(mine, users.OWNER, ANSWERS, NOW)
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        theirs.add(UserSettings(session_minutes=30, session_exercises=6, set_up_on=NOW.date()))
        consent.give(theirs, Category.WALKTHROUGH, NOW)
        walkthrough.keep(theirs, MEMBER, ANSWERS, NOW)
        consent.withdraw(theirs, Category.WALKTHROUGH, NOW)
        assert walkthrough.kept(theirs) is None
        found = theirs.scalars(select(UserSettings)).one()  # settings are training data
        assert (found.session_minutes, found.session_exercises) == (30, 6)
        assert found.set_up_on == NOW.date()
    assert _kept(member, users.OWNER) == 1


def test_a_yes_to_older_wording_keeps_nothing(
    member: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        consent.give(theirs, Category.WALKTHROUGH, NOW)
        monkeypatch.setitem(VERSIONS, Category.WALKTHROUGH, 3)
        assert walkthrough.keep(theirs, MEMBER, ANSWERS, NOW) is False


def test_leaving_takes_the_answers(member: Engine, tmp_path: Path) -> None:
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        consent.give(theirs, Category.WALKTHROUGH, NOW)
        walkthrough.keep(theirs, MEMBER, ANSWERS, NOW)
    with session_scope(make_session_factory(member)) as shared:
        assert erase.leave(shared, MEMBER, tmp_path / left_list.NAME, NOW)
    assert _kept(member, MEMBER) == 0


@pytest.mark.parametrize(
    ("column", "value"),
    [("age_band", "90+"), ("often", "daily"), ("effort", "max"), ("how_long", "an hour")],
)
def test_the_database_refuses_an_answer_it_doesnt_know(
    member: Engine, column: str, value: str
) -> None:
    with (
        pytest.raises(IntegrityError),
        session_scope(make_session_factory(member, user_id=MEMBER)) as theirs,
    ):
        theirs.add(WalkthroughAnswers(version=2, answered_at=NOW, **{column: value}))


def test_the_database_refuses_a_second_row_for_a_person(member: Engine) -> None:
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        theirs.add(WalkthroughAnswers(version=2, answered_at=NOW))
    with (
        pytest.raises(IntegrityError),
        session_scope(make_session_factory(member, user_id=MEMBER)) as theirs,
    ):
        theirs.add(WalkthroughAnswers(version=2, answered_at=NOW))


@pytest.mark.parametrize("count", [None, 4, 6, 8])
def test_exercises_per_session_is_4_6_8_or_as_planned(member: Engine, count: int | None) -> None:
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        theirs.add(UserSettings(session_exercises=count))


def test_the_database_refuses_another_exercise_count(member: Engine) -> None:
    with (
        pytest.raises(IntegrityError),
        session_scope(make_session_factory(member, user_id=MEMBER)) as theirs,
    ):
        theirs.add(UserSettings(session_exercises=5))


def test_the_start_day_and_set_up_day_start_empty(member: Engine) -> None:
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        theirs.add(UserSettings())
        theirs.add(PlanState())
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        assert theirs.scalars(select(PlanState.starts_on)).one() is None
        assert theirs.scalars(select(UserSettings.set_up_on)).one() is None
        theirs.scalars(select(PlanState)).one().starts_on = date(2026, 11, 11)
    with session_scope(make_session_factory(member, user_id=MEMBER)) as theirs:
        assert theirs.scalars(select(PlanState.starts_on)).one() == date(2026, 11, 11)
