"""closing on (ADR-0059): the day a member's data is erased once the multi-user switch is off

Set by the daily wind-down job for each member while `TC_MULTI_USER` is off, 30 days on, and
cleared if it goes back on. Nobody has it yet: only the owner exists, who never closes. Downgrade
drops the column.

Revision ID: a9c3e5f7b1d2
Revises: f6a8c0e2d4b7
Create Date: 2026-11-07 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a9c3e5f7b1d2"
down_revision: str | Sequence[str] | None = "f6a8c0e2d4b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("closing_on", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("closing_on")
