"""the walk-through (ADR-0092): its answers, the plan's start day, exercises per session

A new table, `walkthrough_answers`, one row per person, kept only with `walkthrough` consent.
Three nullable columns: `settings.session_exercises` (4, 6 or 8; ADR-0082 addendum),
`settings.set_up_on` (the day the walk-through was saved) and `plan_state.starts_on` (ADR-0091
addendum). Nothing is copied and no row changes: every new column starts empty, which behaves as
before. `settings` is rebuilt for its new check (batch, keys off, `foreign_key_check` after);
every row and id stays. Downgrade drops the table and the columns, and with them anyone's
answers, start day and exercise count.

Revision ID: a1c3e5f7b9d2
Revises: f9c1e3a5b7d2
Create Date: 2026-11-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c3e5f7b9d2"
down_revision: str | Sequence[str] | None = "f9c1e3a5b7d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "walkthrough_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=False),
        sa.Column("age_band", sa.String(length=8), nullable=True),
        sa.Column("often", sa.String(length=16), nullable=True),
        sa.Column("effort", sa.String(length=16), nullable=True),
        sa.Column("how_long", sa.String(length=16), nullable=True),
        sa.Column("chair", sa.Boolean(), nullable=True),
        sa.Column("stairs", sa.Boolean(), nullable=True),
        sa.Column("walk", sa.Boolean(), nullable=True),
        sa.Column("floor", sa.Boolean(), nullable=True),
        sa.Column("weekdays", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("placement", sa.JSON(), server_default="{}", nullable=False),
        sa.CheckConstraint(
            "age_band IS NULL OR age_band IN ('18-34', '35-49', '50-64', '65-74', '75+')",
            name=op.f("ck_walkthrough_answers_age_band_valid"),
        ),
        sa.CheckConstraint(
            "often IS NULL OR often IN ('not_now', 'under_weekly', 'one_two', 'three_plus')",
            name=op.f("ck_walkthrough_answers_often_valid"),
        ),
        sa.CheckConstraint(
            "effort IS NULL OR effort IN ('talk', 'breathless')",
            name=op.f("ck_walkthrough_answers_effort_valid"),
        ),
        sa.CheckConstraint(
            "how_long IS NULL OR how_long IN ('under_10', '10_30', 'over_30')",
            name=op.f("ck_walkthrough_answers_how_long_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_walkthrough_answers_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_walkthrough_answers")),
        sa.UniqueConstraint("user_id", name=op.f("uq_walkthrough_answers_user_id")),
    )
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("session_exercises", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("set_up_on", sa.Date(), nullable=True))
        batch_op.create_check_constraint(
            "session_exercises_valid", "session_exercises IS NULL OR session_exercises IN (4, 6, 8)"
        )
    with op.batch_alter_table("plan_state", schema=None) as batch_op:
        batch_op.add_column(sa.Column("starts_on", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("plan_state", schema=None) as batch_op:
        batch_op.drop_column("starts_on")
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_settings_session_exercises_valid"), type_="check")
        batch_op.drop_column("set_up_on")
        batch_op.drop_column("session_exercises")
    op.drop_table("walkthrough_answers")
