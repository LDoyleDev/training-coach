"""plans per person (ADR-0073): sessions, their items and plan versions become each person's own

The shared rows become the owner's, keeping their ids, so nothing that points at them moves:
workouts, the queue, a session in progress, events, proposals, a workout kept for /undo or a
Telegram button. Composite keys hold a workout, a queue and a session in progress to the person's
own sessions and versions (`docs/specs/plans-per-person.md`).

It refuses if anyone but the owner exists (Liam, 5 Nov 2026): nobody gets a copy of the owner's
plan, and a new person starts from a starter. A downgrade refuses while anyone else has plan rows;
otherwise the owner's rows become the shared plan again.

Revision ID: b4e8d1f6a9c2
Revises: c8d2e4f6a1b3
Create Date: 2026-11-06 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4e8d1f6a9c2"
down_revision: str | Sequence[str] | None = "c8d2e4f6a1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER = 1
PLAN_TABLES = ("plan_versions", "session_templates", "template_items")
# Table -> its plain key to the plan, the column, the table it points at, on delete.
KEYS = (
    ("template_items", "template_id", "session_templates", "CASCADE"),
    ("workouts", "template_id", "session_templates", "RESTRICT"),
    ("workouts", "plan_version_id", "plan_versions", "RESTRICT"),
    ("plan_state", "next_template_id", "session_templates", "RESTRICT"),
    ("session_progress", "template_id", "session_templates", "CASCADE"),
)
# Each plan table's old unique columns.
UNIQUE = {
    "plan_versions": ("since",),
    "session_templates": ("position", "slug"),
    "template_items": (),
}


def _plain(table: str, column: str, target: str) -> str:
    return f"fk_{table}_{column}_{target}"


def _composite(table: str, target: str) -> str:
    return f"fk_{table}_user_id_{target}"


def _count(db: sa.Connection, table: str, where: str = "") -> int:
    statement = f"SELECT count(*) FROM {table} {where}"  # noqa: S608 - fixed names
    return db.execute(sa.text(statement), {"owner": OWNER}).scalar_one()


def upgrade() -> None:
    db = op.get_bind()
    others = _count(db, "users", "WHERE id != :owner")
    if others:
        raise RuntimeError(
            f"{others} people besides the owner exist: this gives the plan to the owner alone, "
            "and a new person starts from a starter (ADR-0073)"
        )
    has_rows = any(_count(db, table) for table in PLAN_TABLES)
    if has_rows and not _count(db, "users", "WHERE id = :owner"):
        raise RuntimeError("the plan has rows but the owner (user 1) doesn't exist")

    for table in PLAN_TABLES:
        with op.batch_alter_table(table) as batch:
            # Filled with the owner for existing rows; the default is dropped again below.
            batch.add_column(
                sa.Column("user_id", sa.Integer(), nullable=False, server_default=str(OWNER))
            )
            batch.create_index(f"ix_{table}_user_id", ["user_id"])
            batch.create_foreign_key(
                f"fk_{table}_user_id_users", "users", ["user_id"], ["id"], ondelete="CASCADE"
            )
            for column in UNIQUE[table]:
                batch.drop_constraint(f"uq_{table}_{column}", type_="unique")
                batch.create_unique_constraint(f"uq_{table}_user_id_{column}", ["user_id", column])
            if table != "template_items":
                batch.create_unique_constraint(f"uq_{table}_user_id_id", ["user_id", "id"])
        with op.batch_alter_table(table) as batch:
            batch.alter_column("user_id", server_default=None)

    for table, column, target, on_delete in KEYS:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(_plain(table, column, target), type_="foreignkey")
            batch.create_foreign_key(
                _composite(table, target),
                target,
                ["user_id", column],
                ["user_id", "id"],
                ondelete=on_delete,
            )


def downgrade() -> None:
    db = op.get_bind()
    for table in PLAN_TABLES:
        others = _count(db, table, "WHERE user_id != :owner")
        if others:
            raise RuntimeError(
                f"{others} rows of {table} are someone else's: the plan can only become shared "
                "again with the owner's alone"
            )

    for table, column, target, on_delete in KEYS:
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(_composite(table, target), type_="foreignkey")
            batch.create_foreign_key(
                _plain(table, column, target), target, [column], ["id"], ondelete=on_delete
            )

    for table in reversed(PLAN_TABLES):
        with op.batch_alter_table(table) as batch:
            if table != "template_items":
                batch.drop_constraint(f"uq_{table}_user_id_id", type_="unique")
            for column in UNIQUE[table]:
                batch.drop_constraint(f"uq_{table}_user_id_{column}", type_="unique")
                batch.create_unique_constraint(f"uq_{table}_{column}", [column])
            batch.drop_constraint(f"fk_{table}_user_id_users", type_="foreignkey")
            batch.drop_index(f"ix_{table}_user_id")
            batch.drop_column("user_id")
