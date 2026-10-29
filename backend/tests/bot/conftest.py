from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import SETTINGS
from training_coach.bot.app import build_bot
from training_coach.db.session import make_session_factory
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
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
