"""roles (ADR-0059): users gain a role, admin or member, and a label for the admin's list

The owner becomes the one admin; anyone else is a member. Nothing reads either until the
multi-user switch is on (`TC_MULTI_USER`, off by default). Downgrade drops both columns.

Revision ID: e2f4a6c8b0d1
Revises: d7a3f9c1e5b8
Create Date: 2026-11-07 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2f4a6c8b0d1"
down_revision: str | Sequence[str] | None = "d7a3f9c1e5b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNER = 1  # services.users.OWNER


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.String(length=8), nullable=False, server_default="member")
        )
        batch_op.add_column(sa.Column("label", sa.String(length=40), nullable=True))
    op.execute(sa.text("UPDATE users SET role = 'admin' WHERE id = :owner").bindparams(owner=OWNER))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("label")
        batch_op.drop_column("role")
