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


def test_seed_command_logs_reason_and_exits_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import training_coach.__main__ as cli
    from training_coach.services.seed import SeedError

    monkeypatch.setenv("TC_DATABASE_URL", f"sqlite:///{tmp_path / 'fail.db'}")
    monkeypatch.setenv("TC_ENVIRONMENT", "test")
    get_settings.cache_clear()
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")

    errors: list[Exception] = [
        SeedError("sessions ['upper'] exist in the database but not in plan.toml"),
        RuntimeError("disk full"),
    ]
    for error in errors:

        def boom(*_args: object, _error: Exception = error) -> None:
            raise _error

        monkeypatch.setattr(cli, "apply_seed", boom)
        with pytest.raises(SystemExit) as exc:
            main(["seed"])
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "seed.failed" in out
        assert str(error) in out
    get_settings.cache_clear()


def test_noop_seed_logs_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TC_DATABASE_URL", f"sqlite:///{tmp_path / 'noop.db'}")
    monkeypatch.setenv("TC_ENVIRONMENT", "test")
    get_settings.cache_clear()
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")

    main(["seed"])
    assert "seed.applied" in capsys.readouterr().out
    main(["seed"])
    second = capsys.readouterr().out
    assert "seed.unchanged" in second
    assert "seed.applied" not in second
    get_settings.cache_clear()
