"""Connect my AI: OAuth clients, consents, connections, codes and tokens (ADR-0047 C)

Revision ID: a3ed7ed9a1e7
Revises: 120b38add5e6
Create Date: 2026-10-11 18:09:21.739819

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3ed7ed9a1e7"
down_revision: str | Sequence[str] | None = "120b38add5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("redirect_uris", sa.JSON(), nullable=False),
        sa.Column("client_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_clients")),
        sa.UniqueConstraint("client_id", name=op.f("uq_oauth_clients_client_id")),
    )
    with op.batch_alter_table("oauth_clients", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_oauth_clients_client_hash"), ["client_hash"], unique=False
        )

    op.create_table(
        "mcp_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("client_name", sa.String(length=60), nullable=False),
        sa.Column("redirect_uri", sa.String(length=200), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("passkey_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["oauth_clients.id"],
            name=op.f("fk_mcp_connections_client_id_oauth_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["passkey_id"],
            ["passkeys.id"],
            name=op.f("fk_mcp_connections_passkey_id_passkeys"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_mcp_connections_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_connections")),
    )
    with op.batch_alter_table("mcp_connections", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_mcp_connections_client_id"), ["client_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_mcp_connections_passkey_id"), ["passkey_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_mcp_connections_user_id"), ["user_id"], unique=False)

    op.create_table(
        "oauth_codes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("redirect_uri", sa.String(length=200), nullable=False),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["mcp_connections.id"],
            name=op.f("fk_oauth_codes_connection_id_mcp_connections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_codes")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_oauth_codes_code_hash")),
    )
    with op.batch_alter_table("oauth_codes", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_oauth_codes_connection_id"), ["connection_id"], unique=False
        )

    op.create_table(
        "oauth_consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("handle_hash", sa.String(length=64), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("redirect_uri", sa.String(length=200), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(length=500), nullable=True),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("resource", sa.String(length=200), nullable=False),
        sa.Column("client_hash", sa.String(length=64), nullable=False),
        sa.Column("web_session_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["oauth_clients.id"],
            name=op.f("fk_oauth_consents_client_id_oauth_clients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_oauth_consents_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["web_session_id"],
            ["web_sessions.id"],
            name=op.f("fk_oauth_consents_web_session_id_web_sessions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_consents")),
        sa.UniqueConstraint("handle_hash", name=op.f("uq_oauth_consents_handle_hash")),
    )
    with op.batch_alter_table("oauth_consents", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_oauth_consents_client_id"), ["client_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_oauth_consents_client_hash"), ["client_hash"], unique=False
        )

    op.create_table(
        "oauth_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("resource", sa.String(length=200), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "kind IN ('access', 'refresh')", name=op.f("ck_oauth_tokens_kind_valid")
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["mcp_connections.id"],
            name=op.f("fk_oauth_tokens_connection_id_mcp_connections"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_oauth_tokens_token_hash")),
    )
    with op.batch_alter_table("oauth_tokens", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_oauth_tokens_connection_id"), ["connection_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_oauth_tokens_expires_at"), ["expires_at"], unique=False
        )

    with op.batch_alter_table("web_sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("confirmed_passkey_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_web_sessions_confirmed_passkey_id_passkeys"),
            "passkeys",
            ["confirmed_passkey_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("web_sessions", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_web_sessions_confirmed_passkey_id_passkeys"), type_="foreignkey"
        )
        batch_op.drop_column("confirmed_passkey_id")

    with op.batch_alter_table("oauth_tokens", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_oauth_tokens_expires_at"))
        batch_op.drop_index(batch_op.f("ix_oauth_tokens_connection_id"))

    op.drop_table("oauth_tokens")
    with op.batch_alter_table("oauth_consents", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_oauth_consents_client_hash"))
        batch_op.drop_index(batch_op.f("ix_oauth_consents_client_id"))

    op.drop_table("oauth_consents")
    with op.batch_alter_table("oauth_codes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_oauth_codes_connection_id"))

    op.drop_table("oauth_codes")
    with op.batch_alter_table("mcp_connections", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_mcp_connections_user_id"))
        batch_op.drop_index(batch_op.f("ix_mcp_connections_passkey_id"))
        batch_op.drop_index(batch_op.f("ix_mcp_connections_client_id"))

    op.drop_table("mcp_connections")
    with op.batch_alter_table("oauth_clients", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_oauth_clients_client_hash"))

    op.drop_table("oauth_clients")
