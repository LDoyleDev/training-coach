"""session progress place (ADR-0071): where a guided session's kept sets were done

`session_progress.place`, so a day left unsaved is saved in the version its sets were done in,
even after a switch to the other place since. Every row kept so far was kept at home.

Revision ID: 7b38a427bb7c
Revises: b4f9e2a7c1d6
Create Date: 2026-10-28 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7b38a427bb7c"
down_revision: str | Sequence[str] | None = "b4f9e2a7c1d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("session_progress", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("place", sa.String(length=8), server_default="home", nullable=False)
        )
        batch_op.create_check_constraint("place_valid", "place IN ('home', 'gym')")


def downgrade() -> None:
    with op.batch_alter_table("session_progress", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_session_progress_place_valid"), type_="check")
        batch_op.drop_column("place")
