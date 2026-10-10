import json
from datetime import UTC, datetime
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


def test_openapi_command_prints_schema(capsys: pytest.CaptureFixture[str]) -> None:
    main(["openapi"])
    schema = json.loads(capsys.readouterr().out)
    assert "/healthz" in schema["paths"]
    assert set(schema["components"]["schemas"]["Health"]["properties"]) == {
        "status",
        "version",
        "bot_enabled",
    }


def test_no_two_response_models_share_a_name(capsys: pytest.CaptureFixture[str]) -> None:
    """Two models with one name get module-path names in the schema, which renames the web
    app's types under it (two SavedView models in #137)."""
    main(["openapi"])
    names = json.loads(capsys.readouterr().out)["components"]["schemas"]
    assert [n for n in names if "__" in n] == []


def test_openapi_command_ignores_env_and_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The schema depends only on the code: a bad .env or TC_ variable must not matter."""
    main(["openapi"])
    clean = json.loads(capsys.readouterr().out)

    (tmp_path / ".env").write_text("TC_TIMEZONE=Not/AZone\n")
    monkeypatch.chdir(tmp_path)
    main(["openapi"])
    assert json.loads(capsys.readouterr().out) == clean

    monkeypatch.setenv("TC_TIMEZONE", "Not/AZone")
    main(["openapi"])
    assert json.loads(capsys.readouterr().out) == clean


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


def test_backup_command_writes_a_manual_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    monkeypatch.setenv("TC_ENVIRONMENT", "test")
    get_settings.cache_clear()
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")

    main(["backup"])

    (made,) = (tmp_path / "backups").iterdir()
    assert made.name.startswith("training_coach-manual-")
    get_settings.cache_clear()


def test_backup_command_fails_without_a_database_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TC_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("TC_ENVIRONMENT", "test")
    get_settings.cache_clear()
    with pytest.raises(SystemExit):
        main(["backup"])
    get_settings.cache_clear()


def test_backup_command_fails_when_the_database_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TC_DATABASE_URL", f"sqlite:///{tmp_path / 'nope.db'}")
    monkeypatch.setenv("TC_ENVIRONMENT", "test")
    get_settings.cache_clear()
    with pytest.raises(SystemExit):
        main(["backup"])
    assert not (tmp_path / "backups").exists()
    get_settings.cache_clear()


def test_rotate_secrets_reseals_with_the_newest_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from cryptography.fernet import Fernet
    from pydantic import SecretStr

    from training_coach.db.session import make_session_factory, session_scope
    from training_coach.services import ai_key
    from training_coach.services.secret_box import SecretBox
    from training_coach.services.seed import apply_seed, load_plan
    from training_coach.services.users import OWNER

    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    monkeypatch.setenv("TC_DATABASE_URL", url)
    monkeypatch.setenv("TC_ENVIRONMENT", "test")
    get_settings.cache_clear()
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    engine = make_engine(url)
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    with session_scope(make_session_factory(engine, user_id=OWNER)) as session:
        ai_key.store(session, SecretBox(SecretStr(old)), SecretStr("gsk_" + "a" * 40))

    monkeypatch.setenv("TC_SECRETS_KEY", f"{new},{old}")
    get_settings.cache_clear()
    main(["rotate-secrets"])
    assert "Re-sealed 1 key(s)" in capsys.readouterr().out

    with session_scope(make_session_factory(engine, user_id=OWNER)) as session:
        assert ai_key.key(session, SecretBox(SecretStr(new)), datetime.now(UTC)) is not None

    # A secrets key left out of the list: its stored keys can't be opened, and it says so.
    monkeypatch.setenv("TC_SECRETS_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    with pytest.raises(SystemExit, match="1 stored key"):
        main(["rotate-secrets"])
    assert (
        "Re-sealed 0 key(s) with the newest secrets key; 1 unreadable." in capsys.readouterr().out
    )
    engine.dispose()
    monkeypatch.delenv("TC_SECRETS_KEY")
    get_settings.cache_clear()
    with pytest.raises(SystemExit, match="TC_SECRETS_KEY is not set"):
        main(["rotate-secrets"])
    get_settings.cache_clear()
