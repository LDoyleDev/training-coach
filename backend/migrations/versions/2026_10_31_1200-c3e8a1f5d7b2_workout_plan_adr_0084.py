"""a workout's plan (ADR-0082, ADR-0084): the minutes chosen and the sets planned

Two nullable columns on workouts: ``minutes``, the day's "short on time" choice, and
``planned``, exercise slug -> {"sets": N}. Existing rows keep both empty, which reads as done as
planned, every set planned. No data changes; downgrade drops both columns and with them the
plans of workouts saved since (their sets stay).

Revision ID: c3e8a1f5d7b2
Revises: face6f88f5fe
Create Date: 2026-10-31 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e8a1f5d7b2"
down_revision: str | Sequence[str] | None = "face6f88f5fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workouts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("planned", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("workouts", schema=None) as batch_op:
        batch_op.drop_column("planned")
        batch_op.drop_column("minutes")
