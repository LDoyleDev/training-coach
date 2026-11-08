"""The connect link (ADR-0089): codes unique within a link, so a code names one claim; expired
links cleared with their claims."""

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, select

from training_coach.db.models import TelegramLink, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import auth, telegram_link, users

MEMBER = 2


def test_a_clashing_code_is_drawn_again(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime.now(UTC)
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=MEMBER, role=users.MEMBER))
    with session_scope(make_session_factory(engine, user_id=MEMBER)) as mine:
        token = telegram_link.make(mine, now)
    draws: Iterator[int] = iter([111111, 111111, 222222])
    monkeypatch.setattr(telegram_link.secrets, "randbelow", lambda _n: next(draws))
    with session_scope(make_session_factory(engine)) as shared:
        first = telegram_link.claim(shared, token, 7001, "A", now, configured=None)
        second = telegram_link.claim(shared, token, 7002, "B", now, configured=None)
    assert first == telegram_link.Code("111111")
    assert second == telegram_link.Code("222222")


def test_only_expired_links_are_cleared(engine: Engine) -> None:
    now = datetime.now(UTC)
    with session_scope(make_session_factory(engine)) as shared:
        shared.add_all([User(id=MEMBER, role=users.MEMBER), User(id=MEMBER + 1)])
    for person, made in ((MEMBER, now - telegram_link.LINK_TTL), (MEMBER + 1, now)):
        with session_scope(make_session_factory(engine, user_id=person)) as theirs:
            telegram_link.make(theirs, made)
    with session_scope(make_session_factory(engine)) as shared:
        telegram_link.clear_expired(shared, now)
        left = shared.scalars(select(TelegramLink.user_id), execution_options=auth.EVERYONE)
        assert list(left) == [MEMBER + 1]
