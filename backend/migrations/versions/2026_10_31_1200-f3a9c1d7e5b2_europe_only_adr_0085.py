"""europe only (ADR-0085): users gain country and last_seen_in_europe

`country` is the country of residence a person gives (nullable: nobody has been asked yet).
`last_seen_in_europe` is their last signed-in web visit from the EU or EEA; the bot and the MCP
endpoint serve them only for 30 days after it. Every existing person gets the migration time,
so nothing stops on deploy: the owner has 30 days to visit the website from Europe, which any
visit does.

Downgrade drops both columns, losing every country given and every last-seen date (upgrading
again marks everyone seen now, with no country). Restore the pre-deploy backup to keep them
(docs/runbooks/deploy.md, Rollback).

Revision ID: f3a9c1d7e5b2
Revises: b7e1c3d5f9a2
Create Date: 2026-10-31 12:00:00.000000

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a9c1d7e5b2"
down_revision: str | Sequence[str] | None = "b7e1c3d5f9a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("country", sa.String(length=2), nullable=True))
        batch_op.add_column(sa.Column("last_seen_in_europe", sa.DateTime(), nullable=True))
    # Stored naive, in UTC, as db.types.UTCDateTime does.
    now = datetime.now(UTC).replace(tzinfo=None)
    op.get_bind().execute(
        sa.text("UPDATE users SET last_seen_in_europe = :now").bindparams(
            sa.bindparam("now", type_=sa.DateTime())
        ),
        {"now": now},
    )
    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column("last_seen_in_europe", existing_type=sa.DateTime(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("last_seen_in_europe")
        batch_op.drop_column("country")
