"""sound setting (ADR-0062): what the guided timers play at each change; everyone starts at chime

Autogenerate doesn't see check constraints on existing tables; it is added by hand and repeats
the model's values.

Revision ID: 8041ef5f4a10
Revises: 952cfb8cf1df
Create Date: 2026-10-21 10:57:40.132689

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8041ef5f4a10"
down_revision: str | Sequence[str] | None = "952cfb8cf1df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("sound", sa.String(length=16), server_default="chime", nullable=False)
        )
        batch_op.create_check_constraint(
            "sound_valid", "sound IN ('chime', 'beep', 'wood', 'bell', 'none')"
        )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_constraint("sound_valid", type_="check")
        batch_op.drop_column("sound")
