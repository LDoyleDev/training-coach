"""retired sessions (ADR-0093): `session_templates.retired_on`, the day a session left the cycle

A session removed from the cycle while a workout names it is kept, retired: the day it went,
no items, parked at position 10_000 + id. Empty means in the cycle. The column is added with
ADD COLUMN only: no constraint changes, no table rebuild and no row changes, so every session
stays in the cycle, as before. Nothing in the app retires a session yet.

Downgrading refuses while any session is retired: without the column a retired session would
come back into the cycle with no exercises. Otherwise it drops the column (a batch rebuild of
`session_templates`, keys off, `foreign_key_check` after; every row and id stays).

Revision ID: b3d5f7a9c1e4
Revises: a1c3e5f7b9d2
Create Date: 2026-11-10 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d5f7a9c1e4"
down_revision: str | Sequence[str] | None = "a1c3e5f7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("session_templates", sa.Column("retired_on", sa.Date(), nullable=True))


def downgrade() -> None:
    retired = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM session_templates WHERE retired_on IS NOT NULL")
    )
    if retired:
        raise RuntimeError(
            f"Retired sessions: {retired} (ADR-0093). Without retired_on they would come back"
            " into their cycles with no exercises: delete them or put them back before"
            " downgrading"
        )
    with op.batch_alter_table("session_templates", schema=None) as batch_op:
        batch_op.drop_column("retired_on")
