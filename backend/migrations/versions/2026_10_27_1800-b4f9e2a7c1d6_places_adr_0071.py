"""places (ADR-0071): where a person trains, where each workout was done, and gym versions

- `settings.places`: home, gym or both; `settings.place`: the place Today starts at when both.
  Home for everyone, so nothing changes until a person says they train at a gym.
- `workouts.place`: every workout so far was done at home.
- `template_items.place`: which version of a session an item belongs to. Positions now count
  within a version, so the unique key gains the place.

Downgrading drops the gym versions' items (the seed puts them back) and every place recorded.

Revision ID: b4f9e2a7c1d6
Revises: c3e8a1f5d9b2
Create Date: 2026-10-27 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4f9e2a7c1d6"
down_revision: str | Sequence[str] | None = "c3e8a1f5d9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLACE = "place IN ('home', 'gym')"


def _place() -> sa.Column[str]:
    return sa.Column("place", sa.String(length=8), server_default="home", nullable=False)


def upgrade() -> None:
    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("places", sa.String(length=8), server_default="home", nullable=False)
        )
        batch_op.add_column(_place())
        batch_op.create_check_constraint("places_valid", "places IN ('home', 'gym', 'both')")
        batch_op.create_check_constraint("place_valid", PLACE)

    with op.batch_alter_table("workouts", schema=None) as batch_op:
        batch_op.add_column(_place())
        batch_op.create_check_constraint("place_valid", PLACE)

    with op.batch_alter_table("template_items", schema=None) as batch_op:
        batch_op.add_column(_place())
        batch_op.create_check_constraint("place_valid", PLACE)
        batch_op.drop_constraint("uq_template_items_template_id_position", type_="unique")
        batch_op.create_unique_constraint(
            batch_op.f("uq_template_items_template_id_place_position"),
            ["template_id", "place", "position"],
        )


def downgrade() -> None:
    # Nothing refers to a template item, so the gym versions can go; the home ones stay.
    op.execute("DELETE FROM template_items WHERE place = 'gym'")
    with op.batch_alter_table("template_items", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("uq_template_items_template_id_place_position"), type_="unique"
        )
        batch_op.create_unique_constraint(
            batch_op.f("uq_template_items_template_id_position"), ["template_id", "position"]
        )
        batch_op.drop_constraint(batch_op.f("ck_template_items_place_valid"), type_="check")
        batch_op.drop_column("place")

    with op.batch_alter_table("workouts", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_workouts_place_valid"), type_="check")
        batch_op.drop_column("place")

    with op.batch_alter_table("settings", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("ck_settings_place_valid"), type_="check")
        batch_op.drop_constraint(batch_op.f("ck_settings_places_valid"), type_="check")
        batch_op.drop_column("place")
        batch_op.drop_column("places")
