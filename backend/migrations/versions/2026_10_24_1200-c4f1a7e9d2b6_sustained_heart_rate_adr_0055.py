"""sustained heart rate (ADR-0055, 2026-10-24): the highest a band workout held 3 minutes

Revision ID: c4f1a7e9d2b6
Revises: b7e2c4d9a1f3
Create Date: 2026-10-24 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c4f1a7e9d2b6"
down_revision: str | Sequence[str] | None = "b7e2c4d9a1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("imported_workouts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sustained_hr", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "sustained_hr_range", "sustained_hr IS NULL OR sustained_hr BETWEEN 25 AND 250"
        )
    # Workouts from before keep the peak they had, so nobody's zones jump on the deploy; the
    # ceiling over the estimate applies to them too, and the next heart rate in a workout's
    # window counts it again as held.
    op.execute("UPDATE imported_workouts SET sustained_hr = max_hr")


def downgrade() -> None:
    with op.batch_alter_table("imported_workouts", schema=None) as batch_op:
        batch_op.drop_constraint("sustained_hr_range", type_="check")
        batch_op.drop_column("sustained_hr")
