"""the easy start (ADR-0094): five `settings` columns

`easy_start` (the switch, off for everyone), `easy_start_from` (the day it was first turned on or
restarted; empty), `easy_start_weeks_light` and `easy_start_weeks_lower` ("One more easy week"
taps, 0) and `easy_start_told` (the last phase a notice was written for; empty). Every new
column starts off, empty or 0, which behaves as before: nobody's plan changes. `settings` is
rebuilt for the two new checks (batch, keys off, `foreign_key_check` after); every row and id
stays. Downgrade drops the columns, and with them anyone's easy start.

Revision ID: c5e7a9b1d3f6
Revises: b3d5f7a9c1e4
Create Date: 2026-11-17 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5e7a9b1d3f6"
down_revision: str | Sequence[str] | None = "b3d5f7a9c1e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("easy_start", sa.Boolean(), server_default=sa.text("0"), nullable=False)
        )
        batch_op.add_column(sa.Column("easy_start_from", sa.Date(), nullable=True))
        batch_op.add_column(
            sa.Column("easy_start_weeks_light", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("easy_start_weeks_lower", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(sa.Column("easy_start_told", sa.String(length=8), nullable=True))
        batch_op.create_check_constraint(
            "easy_start_weeks_range",
            "easy_start_weeks_light >= 0 AND easy_start_weeks_lower >= 0"
            " AND easy_start_weeks_light + easy_start_weeks_lower <= 2",
        )
        batch_op.create_check_constraint(
            "easy_start_told_valid",
            "easy_start_told IS NULL OR easy_start_told IN ('light', 'lower', 'done')",
        )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_settings_easy_start_told_valid"), type_="check")
        batch_op.drop_constraint(batch_op.f("ck_settings_easy_start_weeks_range"), type_="check")
        batch_op.drop_column("easy_start_told")
        batch_op.drop_column("easy_start_weeks_lower")
        batch_op.drop_column("easy_start_weeks_light")
        batch_op.drop_column("easy_start_from")
        batch_op.drop_column("easy_start")
