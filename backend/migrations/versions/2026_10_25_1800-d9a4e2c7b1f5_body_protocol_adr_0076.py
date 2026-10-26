"""body protocol (ADR-0076): neck and scale body fat, height, thigh landmark, estimate setting

Two new measurement kinds, so the kind check is rebuilt (existing rows are untouched), and three
body settings: height for the tape estimate (empty), how far above the kneecap the thigh is
measured (15 cm), and whether the body-fat estimate is worked out ('off'). Autogenerate doesn't
see check constraints on existing tables; they are written by hand and repeat the model's values.
Downgrade refuses while any neck or scale body-fat measurement exists: the old check would
reject those rows, and dropping them silently would lose the person's data.

Revision ID: d9a4e2c7b1f5
Revises: 4aa795c75305
Create Date: 2026-10-25 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d9a4e2c7b1f5"
down_revision: str | Sequence[str] | None = "4aa795c75305"  # the boxing bell (#347)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_KINDS = "'bodyweight', 'waist', 'chest', 'upper_arm', 'thigh', 'resting_hr'"
NEW_KINDS = (
    "'bodyweight', 'body_fat_scale', 'waist', 'neck', 'chest', 'upper_arm', 'thigh', 'resting_hr'"
)


def upgrade() -> None:
    with op.batch_alter_table("measurements", schema=None) as batch_op:
        batch_op.drop_constraint("kind_valid", type_="check")
        batch_op.create_check_constraint("kind_valid", f"kind IN ({NEW_KINDS})")
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("height_cm", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("thigh_offset_cm", sa.Integer(), server_default="15", nullable=False)
        )
        batch_op.add_column(
            sa.Column(
                "body_fat_estimate", sa.String(length=16), server_default="off", nullable=False
            )
        )
        batch_op.create_check_constraint(
            "height_cm_range", "height_cm IS NULL OR height_cm BETWEEN 120 AND 230"
        )
        batch_op.create_check_constraint(
            "thigh_offset_cm_range", "thigh_offset_cm BETWEEN 5 AND 30"
        )
        batch_op.create_check_constraint(
            "body_fat_estimate_valid", "body_fat_estimate IN ('off', 'navy_male')"
        )


def downgrade() -> None:
    held = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM measurements WHERE kind IN ('neck', 'body_fat_scale')")
    )
    if held:
        raise RuntimeError(
            f"{held} neck or scale body-fat measurements exist: export and delete them before "
            "downgrading"
        )
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_constraint("body_fat_estimate_valid", type_="check")
        batch_op.drop_constraint("thigh_offset_cm_range", type_="check")
        batch_op.drop_constraint("height_cm_range", type_="check")
        batch_op.drop_column("body_fat_estimate")
        batch_op.drop_column("thigh_offset_cm")
        batch_op.drop_column("height_cm")
    with op.batch_alter_table("measurements", schema=None) as batch_op:
        batch_op.drop_constraint("kind_valid", type_="check")
        batch_op.create_check_constraint("kind_valid", f"kind IN ({OLD_KINDS})")
