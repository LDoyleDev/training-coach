"""consents (ADR-0090): a person's yes or withdrawal per category of data, append-only

A new table; nothing is copied. The owner is never asked, so no rows are made for them.
Downgrade drops it.

Revision ID: c3e5a7b9d1f4
Revises: b2d4f6a8c0e3
Create Date: 2026-11-08 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e5a7b9d1f4"
down_revision: str | Sequence[str] | None = "b2d4f6a8c0e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "consents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("answer", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "category IN ('body', 'daily_check', 'band', 'walkthrough')",
            name=op.f("ck_consents_category_valid"),
        ),
        sa.CheckConstraint(
            "answer IN ('given', 'withdrawn')", name=op.f("ck_consents_answer_valid")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_consents_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_consents")),
    )
    op.create_index(op.f("ix_consents_user_id"), "consents", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_consents_user_id"), table_name="consents")
    op.drop_table("consents")
