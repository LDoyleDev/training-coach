"""set load (ADR-0072, builder step 8): `set_logs.load_kg`, the weight a set was done with

Nullable and empty for every set logged so far: bodyweight work has no load, and a step's own
kit (a kettlebell step, a vest step) stays in the step's name. Only a loaded step's sets carry
one. Downgrading drops the column, and with it every weight recorded.

Revision ID: f2c8d5a1b7e3
Revises: e8b3f1a6c2d4
Create Date: 2026-10-26 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2c8d5a1b7e3"
down_revision: str | Sequence[str] | None = "e8b3f1a6c2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("set_logs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("load_kg", sa.Float(), nullable=True))
        batch_op.create_check_constraint(
            "load_kg_range", "load_kg IS NULL OR (load_kg > 0 AND load_kg <= 500)"
        )


def downgrade() -> None:
    with op.batch_alter_table("set_logs", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_set_logs_load_kg_range"), type_="check")
        batch_op.drop_column("load_kg")
