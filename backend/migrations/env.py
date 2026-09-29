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


def _run(connection: Connection) -> None:
    # render_as_batch: SQLite cannot ALTER most columns in place.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = make_engine(database_url)
    with engine.connect() as connection:
        _run(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
