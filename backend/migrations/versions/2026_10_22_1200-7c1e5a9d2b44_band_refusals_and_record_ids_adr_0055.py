"""band refusals and record ids (ADR-0055)

The last sync with the right secret that stored nothing and why, and the HC Webhook version of
the last stored one, so Account can say what went wrong; and the Health Connect id of each
night and workout, which HC Webhook sends from v1.9.23 for edits and deletions. Rows from
before have no id and are still matched as before.

Autogenerate doesn't see check constraints on existing tables; it is added by hand and repeats
the model's values.

Revision ID: 7c1e5a9d2b44
Revises: 8041ef5f4a10
Create Date: 2026-10-22 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c1e5a9d2b44"
down_revision: str | Sequence[str] | None = "8041ef5f4a10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ingest_keys", schema=None) as batch_op:
        batch_op.add_column(sa.Column("refused_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("refused_reason", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("app_version", sa.String(length=32), nullable=True))
        batch_op.create_check_constraint(
            "refused_valid",
            "refused_reason IS NULL OR refused_reason IN"
            " ('too_large', 'not_json', 'failed', 'skipped')",
        )
    for table in ("sleep_sessions", "imported_workouts"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("record_id", sa.String(length=128), nullable=True))
            batch_op.create_index(batch_op.f(f"ix_{table}_record_id"), ["record_id"], unique=False)


def downgrade() -> None:
    for table in ("imported_workouts", "sleep_sessions"):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(f"ix_{table}_record_id"))
            batch_op.drop_column("record_id")
    with op.batch_alter_table("ingest_keys", schema=None) as batch_op:
        batch_op.drop_constraint("refused_valid", type_="check")
        batch_op.drop_column("app_version")
        batch_op.drop_column("refused_reason")
        batch_op.drop_column("refused_at")
