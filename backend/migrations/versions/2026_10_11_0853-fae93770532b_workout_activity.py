"""What a cardio log was: walk, bike... (ux-flow-plan A1)

Revision ID: fae93770532b
Revises: bac2f4510202
Create Date: 2026-10-11 08:53:02.928441

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fae93770532b"
down_revision: str | Sequence[str] | None = "bac2f4510202"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen here: a later change to the enum gets its own migration.
ACTIVITIES = "'walk', 'hike', 'jog', 'run', 'bike', 'swim', 'row', 'stairs', 'other'"


def upgrade() -> None:
    with op.batch_alter_table("workouts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("activity", sa.String(length=16), nullable=True))
        batch_op.create_check_constraint("activity_valid", f"activity IN ({ACTIVITIES})")


def downgrade() -> None:
    with op.batch_alter_table("workouts", schema=None) as batch_op:
        batch_op.drop_constraint("activity_valid", type_="check")
        batch_op.drop_column("activity")
