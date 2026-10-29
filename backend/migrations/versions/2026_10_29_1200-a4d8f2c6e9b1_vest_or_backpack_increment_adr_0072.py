"""vest or backpack increment (ADR-0072): each person's own step for the weight a vest adds

`settings.backpack_increment_kg`: empty keeps the default (1 kg), so nothing changes for anyone
until they set their own. Downgrading drops the step people set.

Revision ID: a4d8f2c6e9b1
Revises: e2c6a9f1b3d7
Create Date: 2026-10-29 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4d8f2c6e9b1"
down_revision: str | Sequence[str] | None = "e2c6a9f1b3d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMN = "backpack_increment_kg"


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column(COLUMN, sa.Float(), nullable=True))
        batch_op.create_check_constraint(
            f"{COLUMN}_range", f"{COLUMN} IS NULL OR {COLUMN} BETWEEN 0.25 AND 20"
        )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f(f"ck_settings_{COLUMN}_range"), type_="check")
        batch_op.drop_column(COLUMN)
