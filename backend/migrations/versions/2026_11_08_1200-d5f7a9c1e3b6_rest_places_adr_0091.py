"""rest places (ADR-0091): `session_templates.rest_after`, the rest days after a session

The queue's rest places (any-level-any-time.md S1, Decided 9) are kept as a count on the
session before them: 0 to 6 rest days after it. Every existing session gets 0, so the queue
behaves as it did: no rows change but the new column. Downgrading drops the column, and with it
any rest places; a queue with rest places then offers its sessions on consecutive days.

Revision ID: d5f7a9c1e3b6
Revises: c3e5a7b9d1f4
Create Date: 2026-11-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5f7a9c1e3b6"
down_revision: str | Sequence[str] | None = "c3e5a7b9d1f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("session_templates", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("rest_after", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.create_check_constraint("rest_after_range", "rest_after BETWEEN 0 AND 6")


def downgrade() -> None:
    with op.batch_alter_table("session_templates", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_session_templates_rest_after_range"), type_="check")
        batch_op.drop_column("rest_after")
