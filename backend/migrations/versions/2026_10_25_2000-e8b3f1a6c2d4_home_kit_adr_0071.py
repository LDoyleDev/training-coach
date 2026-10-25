"""home kit (ADR-0071, builder step 4): an `equipment` row per item a person owns, and when
they last saved their kit

Nothing is filled in: everyone starts with no kit listed (`settings.kit_saved_at` empty), and
with no kit listed no ladder step locks, so the app behaves as before until a person adds their
kit. The check constraints repeat the models' values by hand (autogenerate doesn't see them).
Downgrading drops the table and the column, and with them every kit listed.

Revision ID: e8b3f1a6c2d4
Revises: 4aa795c75305
Create Date: 2026-10-25 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8b3f1a6c2d4"
down_revision: str | Sequence[str] | None = "4aa795c75305"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KITS = (
    "'kettlebell', 'dumbbells', 'pull-up bar', 'dip bars', 'bench', 'band', 'backpack', "
    "'rings', 'mat', 'ab wheel', 'box'"
)


def upgrade() -> None:
    op.create_table(
        "equipment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kit", sa.String(length=32), nullable=False),
        sa.Column("kg", sa.Float(), nullable=True),
        sa.Column("min_kg", sa.Float(), nullable=True),
        sa.Column("resistance", sa.String(length=8), nullable=True),
        sa.Column("note", sa.String(length=40), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(f"kit IN ({KITS})", name=op.f("ck_equipment_kit_valid")),
        sa.CheckConstraint(
            "resistance IS NULL OR resistance IN ('light', 'medium', 'heavy')",
            name=op.f("ck_equipment_resistance_valid"),
        ),
        sa.CheckConstraint(
            "kg IS NULL OR (kg > 0 AND kg <= 100)", name=op.f("ck_equipment_kg_range")
        ),
        sa.CheckConstraint(
            "min_kg IS NULL OR (min_kg > 0 AND min_kg < kg)", name=op.f("ck_equipment_min_kg_range")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_equipment_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_equipment")),
    )
    with op.batch_alter_table("equipment", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_equipment_user_id"), ["user_id"], unique=False)
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("kit_saved_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_column("kit_saved_at")
    with op.batch_alter_table("equipment", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_equipment_user_id"))
    op.drop_table("equipment")
