"""boxing bell (ADR-0074, 2026-10-25): a new timer sound, `ring`, and everyone's default

The check constraint repeats the model's values by hand (autogenerate doesn't see it). Rows
still on the old default, `chime`, move to `ring`: the one person using the app asked for it,
and nobody could tell a chosen chime from the default one. Every other choice is kept.
Downgrading moves `ring` back to `chime`, which the old constraint allows.

Revision ID: 4aa795c75305
Revises: c4f1a7e9d2b6
Create Date: 2026-10-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4aa795c75305"
down_revision: str | Sequence[str] | None = "c4f1a7e9d2b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = "sound IN ('chime', 'beep', 'wood', 'bell', 'none')"
NEW = "sound IN ('ring', 'chime', 'beep', 'wood', 'bell', 'none')"


def _sounds(allowed: str, default: str) -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_constraint("sound_valid", type_="check")
        batch_op.alter_column(
            "sound",
            existing_type=sa.String(length=16),
            existing_nullable=False,
            server_default=default,
        )
        batch_op.create_check_constraint("sound_valid", allowed)


def upgrade() -> None:
    _sounds(NEW, "ring")
    op.execute("UPDATE settings SET sound = 'ring' WHERE sound = 'chime'")


def downgrade() -> None:
    op.execute("UPDATE settings SET sound = 'chime' WHERE sound = 'ring'")
    _sounds(OLD, "chime")
