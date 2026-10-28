"""a level for today (ADR-0080): the guided session keeps the levels chosen for today only

Revision ID: d5a2c7e4b8f1
Revises: b4f9e2a7c1d6
Create Date: 2026-10-27 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5a2c7e4b8f1"
down_revision: str | Sequence[str] | None = "b4f9e2a7c1d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("session_progress", schema=None) as batch_op:
        batch_op.add_column(sa.Column("steps", sa.JSON(), server_default="{}", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("session_progress", schema=None) as batch_op:
        batch_op.drop_column("steps")
