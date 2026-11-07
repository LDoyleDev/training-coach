"""invites (ADR-0059): one-time links an admin makes for someone to join

Shared, not per person: an invite names who made it and, once used, who it became. Only the
token's SHA-256 is kept. Nothing makes or redeems one while `TC_MULTI_USER` is off. Downgrade
drops the table, and with it every open invite.

Revision ID: f6a8c0e2d4b7
Revises: e2f4a6c8b0d1
Create Date: 2026-11-07 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a8c0e2d4b7"
down_revision: str | Sequence[str] | None = "e2f4a6c8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=40), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("used_by", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_invites_created_by_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["used_by"],
            ["users.id"],
            name=op.f("fk_invites_used_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invites")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_invites_token_hash")),
    )


def downgrade() -> None:
    op.drop_table("invites")
