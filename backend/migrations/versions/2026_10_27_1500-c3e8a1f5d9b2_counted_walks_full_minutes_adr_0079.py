"""counted walks' full minutes (ADR-0079): a data migration, no schema change

Until ADR-0079, Count it logged a band workout in which zone 2 dominated as its zone 2 minutes
only (ADR-0055), so a 66-minute walk with 35 minutes in zone 2 was stored as 35. Liam chose
(27 Oct 2026) to fix the stored rows rather than read the import's minutes everywhere, so a
person's own edit of a log always wins. This gives each such set its import's full minutes,
only where the set still holds exactly what the old rule logged: a counted import with zone
minutes, zone 2 at least as long as zones 3-5, one zone2 set whose value equals the import's
zone 2 minutes. Anything edited since is left alone. One statement, no per-row writes.

Downgrade puts the zone 2 minutes back on the sets that match the same rule and now hold the
import's full minutes. It can't tell a set this migration changed from one counted the new way
or edited to exactly the full minutes since; those go back to the zone 2 minutes too, which is
what the old code logged for them.

Revision ID: c3e8a1f5d9b2
Revises: a7d4c2e9f1b3
Create Date: 2026-10-27 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e8a1f5d9b2"
down_revision: str | Sequence[str] | None = "a7d4c2e9f1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The sets the old rule logged: the zone2 set (the only one of its exercise in the workout) of a
# counted import whose zone 2 minutes were at least its zones 3-5, holding the zone 2 minutes
# (going up) or the full minutes (going down). Fixed statements, no input.
FULL_MINUTES = """
    UPDATE set_logs SET value = (
        SELECT iw.minutes FROM imported_workouts AS iw
        WHERE iw.workout_id = set_logs.workout_id AND iw.user_id = set_logs.user_id
    )
    WHERE id IN (
        SELECT s.id FROM set_logs AS s
        JOIN exercises AS e ON e.id = s.exercise_id
        JOIN imported_workouts AS iw ON iw.workout_id = s.workout_id AND iw.user_id = s.user_id
        WHERE iw.status = 'counted'
          AND e.slug = 'zone2'
          AND iw.zone1_min IS NOT NULL AND iw.zone2_min IS NOT NULL AND iw.zone3_min IS NOT NULL
          AND iw.zone4_min IS NOT NULL AND iw.zone5_min IS NOT NULL
          AND iw.zone2_min >= iw.zone3_min + iw.zone4_min + iw.zone5_min
          AND iw.minutes <> iw.zone2_min
          AND s.value = iw.zone2_min
          AND (SELECT count(*) FROM set_logs AS o
               WHERE o.workout_id = s.workout_id AND o.exercise_id = s.exercise_id) = 1
    )
"""
ZONE2_MINUTES = """
    UPDATE set_logs SET value = (
        SELECT iw.zone2_min FROM imported_workouts AS iw
        WHERE iw.workout_id = set_logs.workout_id AND iw.user_id = set_logs.user_id
    )
    WHERE id IN (
        SELECT s.id FROM set_logs AS s
        JOIN exercises AS e ON e.id = s.exercise_id
        JOIN imported_workouts AS iw ON iw.workout_id = s.workout_id AND iw.user_id = s.user_id
        WHERE iw.status = 'counted'
          AND e.slug = 'zone2'
          AND iw.zone1_min IS NOT NULL AND iw.zone2_min IS NOT NULL AND iw.zone3_min IS NOT NULL
          AND iw.zone4_min IS NOT NULL AND iw.zone5_min IS NOT NULL
          AND iw.zone2_min >= iw.zone3_min + iw.zone4_min + iw.zone5_min
          AND iw.minutes <> iw.zone2_min
          AND s.value = iw.minutes
          AND (SELECT count(*) FROM set_logs AS o
               WHERE o.workout_id = s.workout_id AND o.exercise_id = s.exercise_id) = 1
    )
"""


def upgrade() -> None:
    op.execute(sa.text(FULL_MINUTES))


def downgrade() -> None:
    op.execute(sa.text(ZONE2_MINUTES))
