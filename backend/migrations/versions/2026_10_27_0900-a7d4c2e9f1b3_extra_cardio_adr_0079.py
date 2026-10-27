"""extra cardio (ADR-0079): `settings.extra_cardio_min`, minutes a week outside the sessions

Added to the cycle's cardio targets. 0 for everyone, so the targets are the plan's own until a
person sets it. Downgrading drops the column, and with it what each person set.

Revision ID: a7d4c2e9f1b3
Revises: f2c8d5a1b7e3
Create Date: 2026-10-27 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7d4c2e9f1b3"
down_revision: str | Sequence[str] | None = "f2c8d5a1b7e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("extra_cardio_min", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.create_check_constraint(
            "extra_cardio_min_range", "extra_cardio_min BETWEEN 0 AND 600"
        )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_settings_extra_cardio_min_range"), type_="check")
        batch_op.drop_column("extra_cardio_min")
