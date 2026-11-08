"""plan notices (ADR-0087): what a release changed in a person's plan, until they've seen it

Revision ID: d7a3f9c1e5b8
Revises: b4e8d1f6a9c2
Create Date: 2026-11-06 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7a3f9c1e5b8"
down_revision: str | Sequence[str] | None = "b4e8d1f6a9c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan_notices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("told_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_plan_notices_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plan_notices")),
    )
    with op.batch_alter_table("plan_notices") as batch_op:
        batch_op.create_index(batch_op.f("ix_plan_notices_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("plan_notices") as batch_op:
        batch_op.drop_index(batch_op.f("ix_plan_notices_user_id"))
    op.drop_table("plan_notices")
