"""band offers announced in Telegram (ADR-0055)

Revision ID: 5395d39ffac9
Revises: 07d0d154d62c
Create Date: 2026-10-11 19:38:19.030289

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5395d39ffac9"
down_revision: str | Sequence[str] | None = "07d0d154d62c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("imported_workouts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("announced_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("imported_workouts", schema=None) as batch_op:
        batch_op.drop_column("announced_at")
