"""minutes per session (ADR-0082): `settings.session_minutes`, the length every session runs at

Every trimmable session runs at 40, 30 or 20 minutes unless the day picks another length.
Empty for everyone, which is as planned, so nothing changes until a person sets it. No data
changes. Downgrading drops the column, and with it what each person set; a session already
started keeps the minutes its first set fixed.

Revision ID: e5a1c7d3f9b4
Revises: d4f9b2a6e8c1
Create Date: 2026-10-31 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a1c7d3f9b4"
down_revision: str | Sequence[str] | None = "d4f9b2a6e8c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("session_minutes", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "session_minutes_valid", "session_minutes IS NULL OR session_minutes IN (40, 30, 20)"
        )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_settings_session_minutes_valid"), type_="check")
        batch_op.drop_column("session_minutes")
