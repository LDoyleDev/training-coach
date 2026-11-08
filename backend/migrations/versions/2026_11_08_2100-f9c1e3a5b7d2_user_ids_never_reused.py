"""user ids never reused: users gets AUTOINCREMENT

SQLite hands out the highest id plus one, so once the newest member left the next person to join
got their id, and with it anything kept by id outside the database (the bot's drafts and
questions, later the scheduled jobs). AUTOINCREMENT never hands out an id twice. Rebuilds
`users` (batch, keys off, `foreign_key_check` after, as every rebuild); every row and id stays.

The counter starts at the larger of the highest id now and the highest id in the left list
(`left-users.json` beside the database, ADR-0088), so an id freed before this migration isn't
handed out either. A list that can't be read stops the migration rather than guess low.
Downgrade rebuilds `users` without AUTOINCREMENT and drops its counter.

Revision ID: f9c1e3a5b7d2
Revises: e7b9d1f3a5c8
Create Date: 2026-11-08 21:00:00.000000

"""

import json
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f9c1e3a5b7d2"
down_revision: str | Sequence[str] | None = "e7b9d1f3a5c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEFT_LIST = "left-users.json"  # services.left_list.NAME; migrations import no app code


def _highest_left(connection: sa.Connection) -> int:
    """The highest id in the left list beside the database file, 0 without one (an in-memory
    database, no file yet, or an empty list)."""
    database = next(
        (row[2] for row in connection.exec_driver_sql("PRAGMA database_list") if row[1] == "main"),
        "",
    )
    if not database:
        return 0
    found = Path(database).parent / LEFT_LIST
    if not found.exists():
        return 0
    text = found.read_text(encoding="utf-8").strip()
    if not text:
        return 0
    try:
        return max((int(entry["id"]) for entry in json.loads(text)), default=0)
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(
            f"{found} can't be read, so the ids of people who left are unknown: fix it "
            "(backup-restore runbook, ADR-0088) and migrate again"
        ) from exc


def upgrade() -> None:
    connection = op.get_bind()
    left = _highest_left(connection)
    with op.batch_alter_table(
        "users", recreate="always", table_kwargs={"sqlite_autoincrement": True}
    ):
        pass
    highest = connection.exec_driver_sql("SELECT coalesce(max(id), 0) FROM users").scalar_one()
    start = max(highest, left)
    # Copying the rows with their ids already set the counter to the highest; raise it to any
    # id that left before. Written either way, so the counter's row always exists.
    connection.exec_driver_sql("DELETE FROM sqlite_sequence WHERE name = 'users'")
    connection.execute(
        sa.text("INSERT INTO sqlite_sequence (name, seq) VALUES ('users', :start)"),
        {"start": start},
    )


def downgrade() -> None:
    with op.batch_alter_table(
        "users", recreate="always", table_kwargs={"sqlite_autoincrement": False}
    ):
        pass
    op.get_bind().exec_driver_sql("DELETE FROM sqlite_sequence WHERE name = 'users'")
