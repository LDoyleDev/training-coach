"""away, no equipment (ADR-0086): a third place for template items, workouts and progress

`template_items.place`, `workouts.place` and `session_progress.place` allow `away`, a session's
no-equipment version and the days it was done. `settings.place`, the place Today starts at,
stays home or gym: an away day is an exception. No data changes.

Downgrade drops the away versions (plan data the seed writes; nothing refers to an item) and
refuses while any workout or guided-session progress was away: those are a person's records.

Revision ID: a7c2e9f4b1d3
Revises: e5a7c9d1f3b4
Create Date: 2026-11-01 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c2e9f4b1d3"
down_revision: str | Sequence[str] | None = "e5a7c9d1f3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("template_items", "workouts", "session_progress")
WITH_AWAY = "place IN ('home', 'gym', 'away')"
WITHOUT = "place IN ('home', 'gym')"


def _constraint(check: str) -> None:
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(batch_op.f(f"ck_{table}_place_valid"), type_="check")
            batch_op.create_check_constraint("place_valid", check)


def upgrade() -> None:
    _constraint(WITH_AWAY)


def downgrade() -> None:
    bind = op.get_bind()
    for table, count in (
        ("workouts", "SELECT count(*) FROM workouts WHERE place = 'away'"),
        ("session_progress", "SELECT count(*) FROM session_progress WHERE place = 'away'"),
    ):
        held = bind.scalar(sa.text(count))
        if held:
            raise RuntimeError(
                f"{held} rows of {table} were done away (ADR-0086): export them and change or "
                "delete them before downgrading"
            )
    op.execute("DELETE FROM template_items WHERE place = 'away'")
    _constraint(WITHOUT)
