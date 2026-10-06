from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from training_coach.api.app import create_app
from training_coach.config import Settings, get_settings
from training_coach.db.session import make_engine

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", database_url="sqlite:///:memory:")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    """A file-backed SQLite database migrated to head (the real schema, not create_all)."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    get_settings.cache_clear()
    eng = make_engine(url)
    yield eng
    eng.dispose()
    get_settings.cache_clear()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s
