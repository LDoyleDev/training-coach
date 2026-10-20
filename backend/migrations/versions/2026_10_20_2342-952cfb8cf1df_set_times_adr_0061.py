"""set times (ADR-0061)

When a guided session showed each set and when it was confirmed. Sets logged before this, and
every set logged any other way, have none.

Revision ID: 952cfb8cf1df
Revises: 366f833552b1
Create Date: 2026-10-20 23:42:10.841068

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "952cfb8cf1df"
down_revision: str | Sequence[str] | None = "366f833552b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("set_logs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("started_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("done_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("set_logs", schema=None) as batch_op:
        batch_op.drop_column("done_at")
        batch_op.drop_column("started_at")
