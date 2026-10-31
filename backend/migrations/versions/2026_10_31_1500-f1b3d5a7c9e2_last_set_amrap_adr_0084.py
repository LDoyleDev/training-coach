"""last set amrap (ADR-0084): `settings.last_set_amrap`

One switch, off for everyone: no last set runs as many good reps as you can until a person
turns it on. No data changes. Downgrading drops the column, and with it what each person set.

Revision ID: f1b3d5a7c9e2
Revises: d4f9b2a6e8c1
Create Date: 2026-10-31 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1b3d5a7c9e2"
down_revision: str | Sequence[str] | None = "d4f9b2a6e8c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("last_set_amrap", sa.Boolean(), server_default=sa.text("0"), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("last_set_amrap")
