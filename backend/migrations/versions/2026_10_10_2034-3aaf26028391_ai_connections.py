"""ai connections: a person's own Groq key, encrypted (ADR-0047 B)

Revision ID: 3aaf26028391
Revises: 96738c3ade18
Create Date: 2026-10-10 20:34:14.032767

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3aaf26028391"
down_revision: str | Sequence[str] | None = "96738c3ade18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("groq_key", sa.LargeBinary(), nullable=False),
        sa.Column("key_ends", sa.String(length=4), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("share_body", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("share_readiness", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ai_connections_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_connections")),
        sa.UniqueConstraint("user_id", name=op.f("uq_ai_connections_user_id")),
    )


def downgrade() -> None:
    op.drop_table("ai_connections")
