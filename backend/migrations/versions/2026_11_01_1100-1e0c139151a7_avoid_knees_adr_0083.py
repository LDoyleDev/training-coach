"""avoid knees (ADR-0083, #540): `settings.avoid_knees`

"Easy on my knees", the fifth preference: a switch, off for everyone, so no step locks for
anyone until they choose. No data changes. Downgrading drops the column, and with it what each
person chose.

Revision ID: 1e0c139151a7
Revises: a7c2e9f4b1d3
Create Date: 2026-11-01 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1e0c139151a7"
down_revision: str | Sequence[str] | None = "a7c2e9f4b1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("avoid_knees", sa.Boolean(), server_default=sa.text("0"), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("avoid_knees")
