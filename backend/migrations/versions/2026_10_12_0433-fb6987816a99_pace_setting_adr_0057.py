"""pace setting (ADR-0057): how big a step the targets take; everyone starts at standard

Autogenerate doesn't see check constraints on existing tables; it is added by hand and repeats
the model's values.

Revision ID: fb6987816a99
Revises: 7281a9439e79
Create Date: 2026-10-12 04:33:25.322760

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fb6987816a99"
down_revision: str | Sequence[str] | None = "7281a9439e79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("pace", sa.String(length=16), server_default="standard", nullable=False)
        )
        batch_op.create_check_constraint("pace_valid", "pace IN ('steady', 'standard', 'fast')")


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_constraint("pace_valid", type_="check")
        batch_op.drop_column("pace")
