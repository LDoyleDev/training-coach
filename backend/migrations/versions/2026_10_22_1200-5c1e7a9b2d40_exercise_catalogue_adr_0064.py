"""exercise catalogue (ADR-0064): muscles move from the database to the bundled plan

Each exercise's muscles were free tags in ``exercises.muscle_groups``. They are now fixed
muscles with a weight each, read from the bundled plan like an exercise's summary, so the
column goes. Downgrade brings it back empty: the older version's seed fills it on start.

Revision ID: 5c1e7a9b2d40
Revises: 8041ef5f4a10
Create Date: 2026-10-22 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c1e7a9b2d40"
down_revision: str | Sequence[str] | None = "8041ef5f4a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("exercises", schema=None) as batch_op:
        batch_op.drop_column("muscle_groups")


def downgrade() -> None:
    with op.batch_alter_table("exercises", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("muscle_groups", sa.JSON(), server_default="[]", nullable=False)
        )
