"""web session confirmed at (ADR-0049)

Revision ID: bac2f4510202
Revises: 3aaf26028391
Create Date: 2026-10-10 23:55:38.816861

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bac2f4510202"
down_revision: str | Sequence[str] | None = "3aaf26028391"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("web_sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("confirmed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("web_sessions", schema=None) as batch_op:
        batch_op.drop_column("confirmed_at")
