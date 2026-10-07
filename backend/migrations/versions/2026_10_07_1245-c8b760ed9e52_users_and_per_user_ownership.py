"""users and per-user ownership

Revision ID: c8b760ed9e52
Revises: f58870988024
Create Date: 2026-10-07 12:45:34.806839

ADR-0026: a users table, and user_id on every per-person table. Everything that exists today
belongs to user 1 (the owner); the app links user 1 to the allowed Telegram account on start.
The shared plan (exercises, ladders, sessions) has no owner. The single-row checks on plan_state
and settings become one row per user, and exercise_state is keyed by (user_id, exercise_id).
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8b760ed9e52"
down_revision: str | Sequence[str] | None = "f58870988024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER = 1
OWNED = ("workouts", "exercise_state", "plan_state", "settings")


def _rebuild_exercise_state(with_user: bool) -> None:
    """Swap exercise_state's primary key by rebuilding the table explicitly: batch mode can't
    change a primary key without a SQLAlchemy warning (foreign keys are off in migrations)."""
    owner = [sa.Column("user_id", sa.Integer(), nullable=False)] if with_user else []
    owner_fk = (
        [
            sa.ForeignKeyConstraint(
                ["user_id"],
                ["users.id"],
                name=op.f("fk_exercise_state_user_id_users"),
                ondelete="CASCADE",
            )
        ]
        if with_user
        else []
    )
    op.create_table(
        "exercise_state_new",
        *owner,
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("ladder_step_id", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["exercise_id", "ladder_step_id"],
            ["ladder_steps.exercise_id", "ladder_steps.id"],
            name=op.f("fk_exercise_state_exercise_id_ladder_steps"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["exercise_id"],
            ["exercises.id"],
            name=op.f("fk_exercise_state_exercise_id_exercises"),
            ondelete="CASCADE",
        ),
        *owner_fk,
        sa.PrimaryKeyConstraint(
            *(["user_id"] if with_user else []), "exercise_id", name=op.f("pk_exercise_state")
        ),
    )
    columns = "exercise_id, ladder_step_id, updated_at"
    if with_user:
        op.execute(
            sa.text(
                f"INSERT INTO exercise_state_new (user_id, {columns}) "  # noqa: S608 - fixed names
                f"SELECT :owner, {columns} FROM exercise_state"
            ).bindparams(owner=OWNER)
        )
    else:
        op.execute(
            sa.text(
                f"INSERT INTO exercise_state_new ({columns}) "  # noqa: S608 - fixed names
                f"SELECT {columns} FROM exercise_state WHERE user_id = :owner"
            ).bindparams(owner=OWNER)
        )
    op.drop_table("exercise_state")
    op.rename_table("exercise_state_new", "exercise_state")


def _owner_column(batch_op: object, table: str) -> None:
    # Filled with the owner for existing rows; the default is dropped again below.
    batch_op.add_column(  # type: ignore[attr-defined]
        sa.Column("user_id", sa.Integer(), nullable=False, server_default=str(OWNER))
    )
    batch_op.create_foreign_key(  # type: ignore[attr-defined]
        batch_op.f(f"fk_{table}_user_id_users"), "users", ["user_id"], ["id"], ondelete="CASCADE"
    )


def upgrade() -> None:
    users = op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("telegram_user_id", name=op.f("uq_users_telegram_user_id")),
    )
    op.bulk_insert(
        users, [{"id": OWNER, "telegram_user_id": None, "created_at": datetime.now(UTC)}]
    )

    with op.batch_alter_table("workouts") as batch_op:
        _owner_column(batch_op, "workouts")
        batch_op.create_index(batch_op.f("ix_workouts_user_id"), ["user_id"], unique=False)

    _rebuild_exercise_state(with_user=True)

    for table in ("plan_state", "settings"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(batch_op.f(f"ck_{table}_single_row"), type_="check")
            _owner_column(batch_op, table)
            batch_op.create_unique_constraint(batch_op.f(f"uq_{table}_user_id"), ["user_id"])

    # No default owner from here on: a new row must say whose it is.
    for table in ("workouts", "plan_state", "settings"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("user_id", server_default=None)

    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_events_user_id"), ["user_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_events_user_id_users"), "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
    # Every event so far was the owner's, except the seed's, which belongs to no one.
    op.execute(
        sa.text("UPDATE events SET user_id = :owner WHERE kind != 'seed.applied'").bindparams(
            owner=OWNER
        )
    )


def downgrade() -> None:
    # Back to one person: rows of anyone but the owner are deleted.
    for table in (*OWNED, "events"):
        op.execute(
            sa.text(f"DELETE FROM {table} WHERE user_id != :owner").bindparams(owner=OWNER)  # noqa: S608 - fixed table names
        )

    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_events_user_id_users"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_events_user_id"))
        batch_op.drop_column("user_id")

    for table in ("settings", "plan_state"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(batch_op.f(f"fk_{table}_user_id_users"), type_="foreignkey")
            batch_op.drop_constraint(batch_op.f(f"uq_{table}_user_id"), type_="unique")
            batch_op.drop_column("user_id")
            batch_op.create_check_constraint("single_row", "id = 1")

    _rebuild_exercise_state(with_user=False)

    with op.batch_alter_table("workouts") as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_workouts_user_id_users"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_workouts_user_id"))
        batch_op.drop_column("user_id")

    op.drop_table("users")
