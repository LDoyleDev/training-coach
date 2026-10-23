"""cardio details (ADR-0067): effort, distance, heart rate and start time on a cardio log

Revision ID: b7e2c4d9a1f3
Revises: a3d6f0b81c27
Create Date: 2026-10-23 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e2c4d9a1f3"
down_revision: str | Sequence[str] | None = "a3d6f0b81c27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VALID = (
    "(effort IS NULL OR effort BETWEEN 1 AND 10)"
    " AND (distance_m IS NULL OR distance_m BETWEEN 1 AND 300000)"
    " AND (avg_hr IS NULL OR avg_hr BETWEEN 30 AND 230)"
    " AND (max_hr IS NULL OR max_hr BETWEEN 30 AND 230)"
    " AND (avg_hr IS NULL OR max_hr IS NULL OR max_hr >= avg_hr)"
)


def upgrade() -> None:
    with op.batch_alter_table("workouts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("effort", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("distance_m", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("avg_hr", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("max_hr", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch_op.create_check_constraint("cardio_details_valid", VALID)


def downgrade() -> None:
    with op.batch_alter_table("workouts", schema=None) as batch_op:
        batch_op.drop_constraint("cardio_details_valid", type_="check")
        batch_op.drop_column("started_at")
        batch_op.drop_column("max_hr")
        batch_op.drop_column("avg_hr")
        batch_op.drop_column("distance_m")
        batch_op.drop_column("effort")
