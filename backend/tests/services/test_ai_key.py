"""A person's own Groq key (ADR-0047 B): stored encrypted, shown by its last four characters."""

from datetime import UTC, datetime

from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from training_coach.db.models import AiConnection, Event, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import ai_key
from training_coach.services.secret_box import SecretBox
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

BOX = SecretBox(SecretStr(Fernet.generate_key().decode()))
KEY = SecretStr("gsk_" + "a" * 48 + "4f2a")
NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
OLD_KEY = Fernet.generate_key().decode()
NEW_KEY = Fernet.generate_key().decode()


def test_nothing_stored_at_first(session: Session) -> None:
    assert ai_key.status(session) == ai_key.NONE
    assert ai_key.key(session, BOX, NOW) is None
    assert not ai_key.remove(session)
    assert not ai_key.options(session, enabled=True, body=True, readiness=True)
    assert not ai_key.failed(session, NOW)


def test_a_stored_key_is_encrypted_and_comes_back(session: Session) -> None:
    ai_key.store(session, BOX, KEY)
    session.flush()
    row = session.scalars(select(AiConnection)).one()
    assert KEY.get_secret_value().encode() not in row.groq_key
    assert ai_key.status(session) == ai_key.Status(True, "4f2a", True, False, False, False)
    opened = ai_key.key(session, BOX, NOW)
    assert opened is not None
    assert opened.get_secret_value() == KEY.get_secret_value()
    kinds = list(session.scalars(select(Event.kind)))
    assert kinds == ["ai.key_stored"]
    assert all(KEY.get_secret_value() not in str(p) for p in session.scalars(select(Event.payload)))


def test_a_new_key_replaces_the_old_and_clears_a_failure(session: Session) -> None:
    ai_key.store(session, BOX, KEY)
    session.flush()
    assert ai_key.failed(session, NOW)
    assert not ai_key.failed(session, NOW)  # told once
    ai_key.options(session, enabled=False, body=True, readiness=True)
    ai_key.store(session, BOX, SecretStr("gsk_" + "b" * 48 + "9z9z"))
    session.flush()
    assert ai_key.status(session) == ai_key.Status(True, "9z9z", True, True, True, False)
    assert len(list(session.scalars(select(AiConnection)))) == 1


def test_a_key_that_cannot_be_opened_is_marked_failed(session: Session) -> None:
    ai_key.store(session, SecretBox(SecretStr(Fernet.generate_key().decode())), KEY)
    session.flush()
    assert ai_key.key(session, BOX, NOW) is None
    assert ai_key.status(session).failed


def test_removing_the_key(session: Session) -> None:
    ai_key.store(session, BOX, KEY)
    session.flush()
    assert ai_key.remove(session)
    session.flush()
    assert ai_key.status(session) == ai_key.NONE


def test_rotation_reseals_everyones_keys(engine: Engine) -> None:
    old = SecretBox(SecretStr(OLD_KEY))
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
        shared.add(User(id=OWNER + 1))
    for user in (OWNER, OWNER + 1):
        with session_scope(make_session_factory(engine, user_id=user)) as session:
            ai_key.store(session, old, KEY)
    with session_scope(make_session_factory(engine, user_id=OWNER + 1)) as session:
        session.scalars(select(AiConnection)).one().groq_key = b"tampered"
    both = SecretBox(SecretStr(f"{NEW_KEY},{OLD_KEY}"))
    with session_scope(make_session_factory(engine)) as shared:
        assert ai_key.rotate_all(shared, both) == (1, 1)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as session:
        opened = ai_key.key(session, SecretBox(SecretStr(NEW_KEY)), NOW)
    assert opened is not None
