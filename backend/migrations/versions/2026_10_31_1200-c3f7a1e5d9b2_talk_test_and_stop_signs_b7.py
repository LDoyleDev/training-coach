"""talk test and stop signs (spec B7, ADR-0083): `settings.talk_test`, `settings.stop_signs_seen`

Two switches, off for everyone: cardio effort keeps showing as heart-rate zones, and the stop
signs show once before the next guided session. No data changes. Downgrading drops both
columns, and with them what each person set.

Revision ID: c3f7a1e5d9b2
Revises: b7e1c3d5f9a2
Create Date: 2026-10-31 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f7a1e5d9b2"
down_revision: str | Sequence[str] | None = "b7e1c3d5f9a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("talk_test", sa.Boolean(), server_default=sa.text("0"), nullable=False)
        )
        batch_op.add_column(
            sa.Column("stop_signs_seen", sa.Boolean(), server_default=sa.text("0"), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("stop_signs_seen")
        batch_op.drop_column("talk_test")
