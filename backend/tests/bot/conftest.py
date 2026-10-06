import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker
from telegram.ext import Application

from tests.bot.fakes import SETTINGS
from training_coach.bot.app import build_bot
from training_coach.db.session import make_session_factory
from training_coach.services.seed import apply_seed, load_plan


@pytest.fixture
def sessions(engine: Engine) -> sessionmaker[Session]:
    return make_session_factory(engine)


@pytest.fixture
def seeded(sessions: sessionmaker[Session]) -> sessionmaker[Session]:
    with sessions() as session:
        apply_seed(session, load_plan())
        session.commit()
    return sessions


@pytest.fixture
def application(seeded: sessionmaker[Session]) -> Application:  # type: ignore[type-arg]  # see build_bot
    return build_bot(SETTINGS, seeded)
