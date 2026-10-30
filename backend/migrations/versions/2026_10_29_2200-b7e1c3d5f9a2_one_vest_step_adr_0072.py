"""one vest step (ADR-0072): pull-up and chin-up lose their 10 and 15 kg vest steps

Liam chose one "Vest or backpack" step that takes load from 5 kg (29 Oct 2026). The seed can't
shorten a ladder, so this removes the top two steps, "Vest or backpack, 10 kg" and "Vest or
backpack, 15 kg", of `pull-up` and `chin-up`; the seed then renames "Vest or backpack, 5 kg" in
place to "Vest or backpack". Steps are found by exercise slug and name, as ids differ between
databases. Nothing is moved: if anything uses a step that would go (a logged set, someone's
level, a guided session in progress, a replaced workout kept for /undo), it stops before any
write and the whole migration rolls back. Sets logged at the 5 kg step without a weight get
5 kg, what that step was done with.

Downgrade puts the two steps back at the top of each ladder (new ids, no cue: the seed writes
cues) and the 5 kg name on the step below. The 5 kg filled in stays: it is what the sets were.
A set logged at the loaded step after the upgrade keeps its weight, at the 5 kg step: restore
the pre-deploy backup instead to undo that (docs/runbooks/deploy.md, Rollback).

Revision ID: b7e1c3d5f9a2
Revises: a4d8f2c6e9b1
Create Date: 2026-10-29 22:00:00.000000

"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e1c3d5f9a2"
down_revision: str | Sequence[str] | None = "a4d8f2c6e9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXERCISES = ("pull-up", "chin-up")
FIVE = "Vest or backpack, 5 kg"
ONE = "Vest or backpack"  # what the seed renames it to
GONE = ("Vest or backpack, 10 kg", "Vest or backpack, 15 kg")
_IDS = sa.bindparam("ids", expanding=True)
COUNTS = {
    "set_logs": "SELECT count(*) FROM set_logs WHERE ladder_step_id IN :ids",
    "exercise_state": "SELECT count(*) FROM exercise_state WHERE ladder_step_id IN :ids",
}


def _steps(db: sa.Connection, slug: str) -> list[tuple[int, int, str]]:
    """(id, position, name) of an exercise's ladder, easiest first; empty on a fresh database."""
    rows = db.execute(
        sa.text(
            "SELECT s.id, s.position, s.name FROM ladder_steps s"
            " JOIN exercises e ON e.id = s.exercise_id WHERE e.slug = :slug ORDER BY s.position"
        ),
        {"slug": slug},
    )
    return [(row[0], row[1], row[2]) for row in rows]


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _in_use(db: sa.Connection, ids: set[int]) -> list[str]:
    """What uses any of ``ids``, in words; empty when nothing does."""
    found = []
    for table, query in COUNTS.items():
        count = db.execute(sa.text(query).bindparams(_IDS), {"ids": sorted(ids)}).scalar_one()
        if count:
            found.append(f"{count} {table} rows")
    for row_id, steps, sets in db.execute(sa.text("SELECT id, steps, sets FROM session_progress")):
        chosen = set((_json(steps) or {}).values())
        kept = {s.get("step_id") for s in _json(sets) or [] if isinstance(s, dict)}
        if (chosen | kept) & ids:
            found.append(f"session_progress {row_id}")
    for row_id, data in db.execute(sa.text("SELECT id, data FROM replaced_workouts")):
        if {s[1] for s in (_json(data) or {}).get("sets", [])} & ids:
            found.append(f"replaced_workouts {row_id}")
    return found


def upgrade() -> None:
    db = op.get_bind()
    going: dict[int, str] = {}
    fives: list[int] = []
    for slug in EXERCISES:
        steps = _steps(db, slug)
        names = [name for _, _, name in steps]
        if not set(GONE) <= set(names):
            continue  # a fresh database, or one this already ran on
        if names[-3:] != [FIVE, *GONE]:
            raise RuntimeError(f"{slug}: expected the ladder to end {[FIVE, *GONE]}, not {names}")
        going |= {step_id: f"{slug} {name!r}" for step_id, _, name in steps[-2:]}
        fives.append(steps[-3][0])
    if not going:
        return
    used = _in_use(db, set(going))
    if used:
        raise RuntimeError(
            f"steps {sorted(going.values())} are in use ({', '.join(used)}); "
            "moving them onto the vest step needs Liam's OK first"
        )
    fill = "UPDATE set_logs SET load_kg = 5.0 WHERE ladder_step_id IN :ids AND load_kg IS NULL"
    db.execute(sa.text(fill).bindparams(_IDS), {"ids": fives})
    db.execute(
        sa.text("DELETE FROM ladder_steps WHERE id IN :ids").bindparams(_IDS),
        {"ids": sorted(going)},
    )


def downgrade() -> None:
    db = op.get_bind()
    for slug in EXERCISES:
        steps = _steps(db, slug)
        if not steps or steps[-1][2] not in (ONE, FIVE):
            continue  # a fresh database, or one already put back
        top_id, top, _ = steps[-1]
        exercise_id = db.execute(
            sa.text("SELECT id FROM exercises WHERE slug = :slug"), {"slug": slug}
        ).scalar_one()
        db.execute(
            sa.text("UPDATE ladder_steps SET name = :name WHERE id = :id"),
            {"name": FIVE, "id": top_id},
        )
        for offset, name in enumerate(GONE, start=1):
            db.execute(
                sa.text(
                    "INSERT INTO ladder_steps (exercise_id, position, name)"
                    " VALUES (:exercise, :position, :name)"
                ),
                {"exercise": exercise_id, "position": top + offset, "name": name},
            )
