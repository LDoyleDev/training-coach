"""Alembic environment. The database URL always comes from application settings."""

from logging.config import fileConfig
from typing import Any

from alembic import context
from alembic.autogenerate.api import AutogenContext
from sqlalchemy import Connection

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


def run_migrations_online() -> None:
    engine = make_engine(database_url)
    with engine.connect() as connection:
        if connection.dialect.name != "sqlite":
            _run(connection, check_foreign_keys=False)
            return
        # Batch mode rebuilds a table by dropping it; with foreign keys on, that drop cascades
        # and deletes child rows (e.g. every set_log of a rebuilt workouts table). The pragma
        # only takes effect outside a transaction, so switch it off first and back on after,
        # whatever happens; foreign_key_check inside the transaction catches anything dangling.
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        try:
            _run(connection, check_foreign_keys=True)
        finally:
            connection.rollback()
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
