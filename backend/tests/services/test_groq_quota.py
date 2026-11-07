"""The shared Groq key's daily cap (ADR-0059, H1): members have one, counted from their own
local midnight, only for calls Groq answered; the owner has none."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, select

from training_coach.db.models import Event, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import groq_quota
from training_coach.services.users import OWNER

BERLIN = ZoneInfo("Europe/Berlin")
NOON = datetime(2026, 11, 7, 11, tzinfo=UTC)  # 12:00 in Berlin


def _member(engine: Engine) -> int:
    with session_scope(make_session_factory(engine)) as shared:
        person = User(role="member")
        shared.add(person)
        shared.flush()
        return person.id


def _take(engine: Engine, user: int, now: datetime = NOON) -> bool:
    """Ask, and use it when allowed, as the bot does with an answer from Groq."""
    with session_scope(make_session_factory(engine, user_id=user)) as bound:
        allowed = groq_quota.left(bound, now, BERLIN)
        if allowed:
            groq_quota.count(bound, now)
        return allowed


def test_asking_spends_nothing(engine: Engine) -> None:
    member = _member(engine)
    with session_scope(make_session_factory(engine, user_id=member)) as bound:
        assert all(groq_quota.left(bound, NOON, BERLIN) for _ in range(groq_quota.MEMBER_CAP + 1))


def test_a_member_has_twenty_a_day(engine: Engine) -> None:
    member = _member(engine)
    assert all(_take(engine, member) for _ in range(groq_quota.MEMBER_CAP))
    assert not _take(engine, member)
    assert not _take(engine, member)  # a no isn't counted, and stays a no


def test_the_count_starts_again_at_local_midnight(engine: Engine) -> None:
    member = _member(engine)
    late = datetime(2026, 11, 7, 22, 30, tzinfo=UTC)  # 23:30 in Berlin
    for _ in range(groq_quota.MEMBER_CAP):
        _take(engine, member, late)
    assert not _take(engine, member, late)
    assert _take(engine, member, late + timedelta(hours=1))  # 00:30 the next day


def test_each_members_count_is_their_own(engine: Engine) -> None:
    one, two = _member(engine), _member(engine)
    for _ in range(groq_quota.MEMBER_CAP):
        _take(engine, one)
    assert not _take(engine, one)
    assert _take(engine, two)


def test_the_owner_has_no_cap_and_nothing_is_counted(engine: Engine) -> None:
    assert all(_take(engine, OWNER) for _ in range(groq_quota.MEMBER_CAP + 5))
    with make_session_factory(engine, user_id=OWNER)() as bound:
        assert bound.scalars(select(Event).where(Event.kind == groq_quota.USED)).all() == []
