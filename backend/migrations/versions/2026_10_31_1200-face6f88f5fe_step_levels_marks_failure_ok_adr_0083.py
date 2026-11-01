"""step levels, marks and failure_ok (ADR-0083, ADR-0084)

`ladder_steps.level` (who a step is for, 1-6), `ladder_steps.marks` (floor, kneeling, impact,
hanging, balance) and `exercises.failure_ok` (a last set to failure is safe on it). Schema only:
no rows are rewritten. The seed fills all three from plan.toml on the next start (the container
runs `alembic upgrade head` then `training-coach seed`), as it does for cues; until then a
step's level is empty, its marks `[]` and failure_ok false, and nothing reads them yet.

Downgrade drops the columns; the seed writes them again after the next upgrade.

Revision ID: face6f88f5fe
Revises: c3f7a1e5d9b2
Create Date: 2026-10-31 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "face6f88f5fe"
down_revision: str | Sequence[str] | None = "c3f7a1e5d9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("exercises", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("failure_ok", sa.Boolean(), server_default=sa.text("0"), nullable=False)
        )
    with op.batch_alter_table("ladder_steps", schema=None) as batch_op:
        batch_op.add_column(sa.Column("level", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("marks", sa.JSON(), server_default="[]", nullable=False))
        batch_op.create_check_constraint("level_range", "level IS NULL OR level BETWEEN 1 AND 6")


def downgrade() -> None:
    with op.batch_alter_table("ladder_steps", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_ladder_steps_level_range"), type_="check")
        batch_op.drop_column("marks")
        batch_op.drop_column("level")
    with op.batch_alter_table("exercises", schema=None) as batch_op:
        batch_op.drop_column("failure_ok")
