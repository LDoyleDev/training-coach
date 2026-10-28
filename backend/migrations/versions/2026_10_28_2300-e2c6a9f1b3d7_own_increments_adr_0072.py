"""own increments (ADR-0072): each person's smallest weight step for each loaded kit

`settings.barbell_increment_kg`, `settings.dumbbells_increment_kg` and
`settings.machine_increment_kg`: empty keeps the default (2.5, 2 and 5 kg), so nothing changes
for anyone until they set their own. Downgrading drops the steps people set.

Revision ID: e2c6a9f1b3d7
Revises: 7b38a427bb7c
Create Date: 2026-10-28 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2c6a9f1b3d7"
down_revision: str | Sequence[str] | None = "7b38a427bb7c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KITS = ("barbell", "dumbbells", "machine")


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        for kit in KITS:
            column = f"{kit}_increment_kg"
            batch_op.add_column(sa.Column(column, sa.Float(), nullable=True))
            batch_op.create_check_constraint(
                f"{column}_range", f"{column} IS NULL OR {column} BETWEEN 0.25 AND 20"
            )


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        for kit in reversed(KITS):
            column = f"{kit}_increment_kg"
            batch_op.drop_constraint(batch_op.f(f"ck_settings_{column}_range"), type_="check")
            batch_op.drop_column(column)
