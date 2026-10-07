"""Alembic environment. The database URL always comes from application settings."""

from logging.config import fileConfig
from typing import Any

from alembic import context
from alembic.autogenerate.api import AutogenContext
from sqlalchemy import Connection, Engine, event

from training_coach.config import get_settings
from training_coach.db import models  # noqa: F401  (registers every model on Base.metadata)
from training_coach.db.base import Base
from training_coach.db.session import make_engine
from training_coach.db.types import UTCDateTime

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata
database_url = get_settings().database_url


def render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | bool:
    """Render app-specific column types as plain SQLAlchemy types.

    Migrations must never import application code: an applied migration has to keep working
    even if ``training_coach.db.types`` changes later.
    """
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime()"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        render_item=render_item,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection, *, check_foreign_keys: bool) -> None:
    # render_as_batch: SQLite cannot ALTER most columns in place. SQLite DDL is transactional,
    # so one transaction covers the whole run and a failed check below rolls all of it back.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        render_item=render_item,
        transactional_ddl=True,
    )
    with context.begin_transaction():
        context.run_migrations()
        if check_foreign_keys:
            broken = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if broken:
                raise RuntimeError(f"migration left broken foreign keys: {broken[:5]}")


def _real_sqlite_transactions(engine: Engine) -> None:
    """Python's sqlite3 only opens a transaction at the first INSERT/UPDATE/DELETE, so a
    migration starting with CREATE TABLE committed it at once and a later failure left it
    behind (the retry then failed on "table already exists"). Take transactions out of the
    driver's hands and emit BEGIN ourselves (SQLAlchemy's pysqlite recipe)."""

    @event.listens_for(engine, "connect")
    def _driver_autocommit(dbapi_connection: Any, _record: Any) -> None:
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(connection: Connection) -> None:
        connection.exec_driver_sql("BEGIN")


def run_migrations_online() -> None:
    engine = make_engine(database_url)
    if engine.dialect.name == "sqlite":
        _real_sqlite_transactions(engine)
    with engine.connect() as connection:
        if connection.dialect.name != "sqlite":
            _run(connection, check_foreign_keys=False)
            return
        # Batch mode rebuilds a table by dropping it; with foreign keys on, that drop cascades
        # and deletes child rows (e.g. every set_log of a rebuilt workouts table). The pragma
        # only takes effect outside a transaction, so it runs on the driver connection (in
        # autocommit) before the migration's transaction and after it, whatever happens;
        # foreign_key_check inside the transaction catches anything dangling.
        driver = connection.connection.driver_connection
        assert driver is not None  # noqa: S101 - a live connection always has one
        driver.execute("PRAGMA foreign_keys=OFF")
        try:
            _run(connection, check_foreign_keys=True)
        finally:
            if connection.in_transaction():
                connection.rollback()
            driver.execute("PRAGMA foreign_keys=ON")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
