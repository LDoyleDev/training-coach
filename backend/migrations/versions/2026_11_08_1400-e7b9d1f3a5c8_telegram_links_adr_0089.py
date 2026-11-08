"""telegram links (ADR-0089): a member connects their Telegram, confirmed with a code on Account

Two new tables, `telegram_links` (a member's connect link, hashed) and `telegram_claims` (who
opened it in Telegram and the code they were sent, hashed), and two columns on `users`: when a
member connected and the Telegram first name it had then. Nobody has a link yet and the owner's
account stays set on the server, so the columns start empty. Downgrade drops them all.

Revision ID: e7b9d1f3a5c8
Revises: d5f7a9c1e3b6
Create Date: 2026-11-08 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7b9d1f3a5c8"
down_revision: str | Sequence[str] | None = "d5f7a9c1e3b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("wrong_codes", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_telegram_links_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_links")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_telegram_links_token_hash")),
    )
    op.create_index(op.f("ix_telegram_links_user_id"), "telegram_links", ["user_id"], unique=False)
    op.create_table(
        "telegram_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("link_id", sa.Integer(), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["link_id"],
            ["telegram_links.id"],
            name=op.f("fk_telegram_claims_link_id_telegram_links"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_telegram_claims_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_claims")),
        sa.UniqueConstraint(
            "link_id", "code_hash", name=op.f("uq_telegram_claims_link_id_code_hash")
        ),
        sa.UniqueConstraint(
            "link_id",
            "telegram_user_id",
            name=op.f("uq_telegram_claims_link_id_telegram_user_id"),
        ),
    )
    op.create_index(
        op.f("ix_telegram_claims_link_id"), "telegram_claims", ["link_id"], unique=False
    )
    op.create_index(
        op.f("ix_telegram_claims_user_id"), "telegram_claims", ["user_id"], unique=False
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("telegram_linked_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("telegram_name", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("telegram_name")
        batch_op.drop_column("telegram_linked_at")
    op.drop_index(op.f("ix_telegram_claims_user_id"), table_name="telegram_claims")
    op.drop_index(op.f("ix_telegram_claims_link_id"), table_name="telegram_claims")
    op.drop_table("telegram_claims")
    op.drop_index(op.f("ix_telegram_links_user_id"), table_name="telegram_links")
    op.drop_table("telegram_links")
