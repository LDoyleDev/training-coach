"""readiness answers (ADR-0046)

Revision ID: 96738c3ade18
Revises: 67b704aac1e8
Create Date: 2026-10-10 16:20:44.918757

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "96738c3ade18"
down_revision: str | Sequence[str] | None = "67b704aac1e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "readiness_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_readiness_answers_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_readiness_answers")),
        sa.UniqueConstraint("user_id", name=op.f("uq_readiness_answers_user_id")),
    )


def downgrade() -> None:
    op.drop_table("readiness_answers")
