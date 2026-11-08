from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import MEMBER as TELEGRAM_MEMBER
from tests.bot.fakes import MULTI, SETTINGS
from tests.bot.fakes import OWNER as TELEGRAM_OWNER
from training_coach.bot.app import build_bot
from training_coach.db.models import User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import users
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    """The owner's sessions, with the owner linked to Telegram account OWNER as start-up does:
    the sender gate finds people by their link (ADR-0089)."""
    with session_scope(make_session_factory(engine)) as shared:
        users.link_owner(shared, TELEGRAM_OWNER)
    return make_session_factory(engine, user_id=OWNER)


@pytest.fixture
def broken() -> Iterator[sessionmaker[Session]]:
    """Owner sessions on an empty in-memory database: every read fails. Disposed afterwards,
    so its connection is closed rather than left to the garbage collector."""
    empty = create_engine("sqlite://")
    yield make_session_factory(empty, user_id=OWNER)
    empty.dispose()


@pytest.fixture
def seeded(sessions: sessionmaker[Session]) -> sessionmaker[Session]:
    with sessions() as session:
        apply_seed(session, load_plan())
        session.commit()
    return sessions


@pytest.fixture
def application(seeded: sessionmaker[Session]) -> Application:  # type: ignore[type-arg]  # see build_bot
    return build_bot(SETTINGS, seeded)


@pytest.fixture
def member(seeded: sessionmaker[Session]) -> sessionmaker[Session]:
    """A member's sessions (ADR-0059), linked to Telegram account MEMBER, with their own plan:
    a copy of the owner's cycle at its starting levels, not a starter (any-level S1), so each
    test compares like with like and no rest day falls on today."""
    engine = seeded.kw["bind"]
    with session_scope(make_session_factory(engine)) as shared:
        person = User(role=users.MEMBER, telegram_user_id=TELEGRAM_MEMBER)
        shared.add(person)
        shared.flush()
        person_id = person.id
        apply_seed(shared, load_plan().model_copy(update={"new_people": None}))
    return make_session_factory(engine, user_id=person_id)


@pytest.fixture
def both(seeded: sessionmaker[Session], member: sessionmaker[Session]) -> Application:  # type: ignore[type-arg]  # see build_bot
    """The bot with TC_MULTI_USER on: the owner and the member are each served."""
    return build_bot(MULTI, seeded)
