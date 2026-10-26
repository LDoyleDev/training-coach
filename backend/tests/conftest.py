import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from training_coach.api.app import create_app
from training_coach.config import Settings, get_settings
from training_coach.db.session import make_engine, make_session_factory
from training_coach.services.users import OWNER

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="test", database_url="sqlite:///:memory:")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def migrated_database(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A SQLite file migrated to head once per test process (each xdist worker has its own).

    Running every migration for each test was most of the suite's time; `engine` copies this.
    """
    folder = tmp_path_factory.mktemp("migrated")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("TC_DATABASE_URL", f"sqlite:///{folder / 'upgrade.db'}")
        get_settings.cache_clear()
        command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    get_settings.cache_clear()
    # The backup API reads through the WAL, so the snapshot is complete and self-contained
    # even though alembic's engine still holds the upgraded file open.
    snapshot = folder / "head.db"
    with (
        closing(sqlite3.connect(folder / "upgrade.db")) as source,
        closing(sqlite3.connect(snapshot)) as target,
    ):
        source.backup(target)
    return snapshot


@pytest.fixture
def engine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, migrated_database: Path
) -> Iterator[Engine]:
    """A file-backed SQLite database migrated to head (the real schema, not create_all)."""
    path = tmp_path / "test.db"
    shutil.copyfile(migrated_database, path)
    url = f"sqlite:///{path}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    get_settings.cache_clear()
    eng = make_engine(url)
    yield eng
    eng.dispose()
    get_settings.cache_clear()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Bound to the owner (user 1, created by the migrations), as the app's sessions are."""
    with make_session_factory(engine, user_id=OWNER)() as s:
        yield s
