"""The band import secret (ADR-0054): made once, kept hashed, found in an unbound session."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine

from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import ingest_keys
from training_coach.services.users import OWNER

NOW = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)


def _make(engine: Engine) -> str:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        return ingest_keys.make(mine, NOW)


def _owner(engine: Engine, secret: str, now: datetime = NOW) -> int | None:
    with session_scope(make_session_factory(engine)) as shared:
        return ingest_keys.owner_of(shared, secret, now)


def test_a_secret_names_its_owner_and_nothing_else_does(engine: Engine) -> None:
    secret = _make(engine)
    assert _owner(engine, secret) == OWNER
    assert _owner(engine, secret + "x") is None
    assert _owner(engine, secret.removeprefix("tci_")) is None
    assert _owner(engine, "tci_" + "a" * 200) is None


def test_last_use_is_noted_at_most_hourly(engine: Engine) -> None:
    secret = _make(engine)
    _owner(engine, secret)
    _owner(engine, secret, NOW + timedelta(minutes=30))
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert ingest_keys.status(mine).last_used_at == NOW
    _owner(engine, secret, NOW + timedelta(minutes=61))
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert ingest_keys.status(mine).last_used_at == NOW + timedelta(minutes=61)


def test_removing_when_there_is_none(engine: Engine) -> None:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert ingest_keys.remove(mine) is False
        assert ingest_keys.status(mine) == ingest_keys.Status(False, None, None)
