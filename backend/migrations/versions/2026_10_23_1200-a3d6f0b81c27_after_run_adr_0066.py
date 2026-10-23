"""after the run (ADR-0066): a block after a session's cardio joins that day's workout

Revision ID: a3d6f0b81c27
Revises: 5c1e7a9b2d40
Create Date: 2026-10-23 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3d6f0b81c27"
down_revision: str | Sequence[str] | None = "5c1e7a9b2d40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("session_progress", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("after_run", sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("session_progress", schema=None) as batch_op:
        batch_op.drop_column("after_run")
