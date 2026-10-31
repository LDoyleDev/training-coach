"""short on time today (ADR-0082): a guided session's chosen length and what its first set fixed

Two nullable JSON columns on session_progress: ``length``, the day's choice (minutes and the
exercises kept), and ``fixed``, the set counts, minutes and pace kept with the first set. Existing
rows keep both empty, which reads as as planned. No data changes; downgrade drops both columns,
so a session in progress on a shorter day then runs as planned.

Revision ID: d4f9b2a6e8c1
Revises: c3e8a1f5d7b2
Create Date: 2026-10-31 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f9b2a6e8c1"
down_revision: str | Sequence[str] | None = "c3e8a1f5d7b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("session_progress", schema=None) as batch_op:
        batch_op.add_column(sa.Column("length", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("fixed", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("session_progress", schema=None) as batch_op:
        batch_op.drop_column("fixed")
        batch_op.drop_column("length")
