"""readiness on the device (ADR-0085): drop the stored answers, keep only when and which version

ADR-0085 supersedes ADR-0046's storage: the ten new questions are answered in the browser and
their answers never reach the server. `readiness_answers` (the seven old questions' answers,
health data) goes; `readiness_checks` keeps one row per person with the questions' version and
when they were answered. Nothing is copied: the old answers were to version 1, which version 2
asks again anyway. Downgrade recreates the old table empty (the answers can't come back: the
old app then asks its questions again) and drops the new one.

Revision ID: b2d4f6a8c0e3
Revises: a9c3e5f7b1d2
Create Date: 2026-11-08 01:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d4f6a8c0e3"
down_revision: str | Sequence[str] | None = "a9c3e5f7b1d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "readiness_checks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_readiness_checks_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_readiness_checks")),
        sa.UniqueConstraint("user_id", name=op.f("uq_readiness_checks_user_id")),
    )
    op.drop_table("readiness_answers")


def downgrade() -> None:
    op.create_table(
        "readiness_answers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_readiness_answers_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_readiness_answers")),
        sa.UniqueConstraint("user_id", name=op.f("uq_readiness_answers_user_id")),
    )
    op.drop_table("readiness_checks")
