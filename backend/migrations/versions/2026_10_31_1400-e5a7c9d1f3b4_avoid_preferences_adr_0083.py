"""avoid preferences (ADR-0083): `settings.avoid_floor`, `avoid_kneeling`, `avoid_impact`,
`avoid_hanging`

Four switches, off for everyone, so no step locks for anyone until they choose. No data
changes. Downgrading drops the columns, and with them what each person chose.

Revision ID: e5a7c9d1f3b4
Revises: e5a1c7d3f9b4
Create Date: 2026-10-31 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a7c9d1f3b4"
down_revision: str | Sequence[str] | None = "e5a1c7d3f9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMNS = ("avoid_floor", "avoid_kneeling", "avoid_impact", "avoid_hanging")


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        for name in COLUMNS:
            batch_op.add_column(
                sa.Column(name, sa.Boolean(), server_default=sa.text("0"), nullable=False)
            )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        for name in reversed(COLUMNS):
            batch_op.drop_column(name)
