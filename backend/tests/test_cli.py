from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from training_coach.__main__ import main
from training_coach.config import get_settings
from training_coach.db.models import SessionTemplate
from training_coach.db.session import make_engine

BACKEND = Path(__file__).resolve().parents[1]


def test_seed_command_loads_plan_twice_safely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    monkeypatch.setenv("TC_ENVIRONMENT", "test")
    get_settings.cache_clear()
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")

    main(["seed"])
    main(["seed"])

    engine = make_engine(url)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(SessionTemplate)) == 7
    engine.dispose()
    get_settings.cache_clear()


def test_unknown_command_rejected() -> None:
    with pytest.raises(SystemExit):
        main(["dance"])
