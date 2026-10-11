"""heart-rate zones (ADR-0054): zone minutes on imported workouts, birth year and own max HR

Autogenerate doesn't see check constraints on existing tables; they are added by hand and
repeat the models' bounds.

Revision ID: 07d0d154d62c
Revises: 44d2f0507a7f
Create Date: 2026-10-11 19:22:51.872114

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "07d0d154d62c"
down_revision: str | Sequence[str] | None = "44d2f0507a7f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ZONES = ("zone1_min", "zone2_min", "zone3_min", "zone4_min", "zone5_min")


def upgrade() -> None:
    with op.batch_alter_table("imported_workouts", schema=None) as batch_op:
        for column in ZONES:
            batch_op.add_column(sa.Column(column, sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "zone_minutes_range",
            "zone1_min IS NULL OR (zone1_min BETWEEN 0 AND 1440 AND zone2_min BETWEEN 0 AND 1440"
            " AND zone3_min BETWEEN 0 AND 1440 AND zone4_min BETWEEN 0 AND 1440"
            " AND zone5_min BETWEEN 0 AND 1440)",
        )

    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("birth_year", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("max_hr", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "birth_year_range", "birth_year IS NULL OR birth_year BETWEEN 1920 AND 2020"
        )
        batch_op.create_check_constraint(
            "max_hr_range", "max_hr IS NULL OR max_hr BETWEEN 120 AND 230"
        )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_constraint("max_hr_range", type_="check")
        batch_op.drop_constraint("birth_year_range", type_="check")
        batch_op.drop_column("max_hr")
        batch_op.drop_column("birth_year")

    with op.batch_alter_table("imported_workouts", schema=None) as batch_op:
        batch_op.drop_constraint("zone_minutes_range", type_="check")
        for column in reversed(ZONES):
            batch_op.drop_column(column)
