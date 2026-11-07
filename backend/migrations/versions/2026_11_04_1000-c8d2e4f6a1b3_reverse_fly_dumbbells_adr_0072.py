"""reverse fly on dumbbells (ADR-0072): the reverse fly loses its "3 s lowering" step

Liam (4 Nov 2026) does the reverse fly with dumbbells of varying weight now, not one 8 kg
kettlebell in one hand. The ladder becomes water bottles, then "Chest on bench/bed, dumbbells",
a step that takes load; the 3 s lowering step on the kettlebell goes, as heavier dumbbells take
its place. The seed can't shorten a ladder, so this removes the top step, "Chest-supported, 3 s
lowering", of `reverse-fly`; the seed then renames "Chest on bench/bed, 8 kg one arm" in place
to the dumbbell step. Steps are found by exercise slug and name, as ids differ between
databases. Nothing is moved: if anything uses the step that would go (a logged set, someone's
level, a level chosen for today, a kept set of a session in progress, a replaced workout kept
for /undo, an event naming it), it stops before any write and the whole migration rolls back.
Sets at the 8 kg step keep no weight: none were logged there on the Pi (checked 4 Nov), and a
kettlebell's 8 kg in one hand isn't a dumbbell's per hand.

Downgrade puts the step back at the top of the ladder (a new id, level 5, no cue: the seed
writes cues) and the 8 kg name on the step below. A set logged at the dumbbell step after the
upgrade stays there under the 8 kg name: restore the pre-deploy backup instead to undo that
(docs/runbooks/deploy.md, Rollback).

Revision ID: c8d2e4f6a1b3
Revises: f3a9c1d7e5b2
Create Date: 2026-11-04 10:00:00.000000

"""

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d2e4f6a1b3"
down_revision: str | Sequence[str] | None = "f3a9c1d7e5b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SLUG = "reverse-fly"
EIGHT = "Chest on bench/bed, 8 kg one arm"
DUMBBELLS = "Chest on bench/bed, dumbbells"  # what the seed renames it to
GONE = "Chest-supported, 3 s lowering"
GONE_LEVEL = 5  # its level in plan.toml before this change
_IDS = sa.bindparam("ids", expanding=True)
COUNTS = {
    "set_logs": "SELECT count(*) FROM set_logs WHERE ladder_step_id IN :ids",
    "exercise_state": "SELECT count(*) FROM exercise_state WHERE ladder_step_id IN :ids",
}
EVENT_KEYS = ("step_id", "from_step_id", "to_step_id")


def _ladder(db: sa.Connection) -> tuple[int | None, list[tuple[int, int, str]]]:
    """The exercise's id and its (id, position, name) steps, easiest first; (None, []) when the
    exercise isn't in the database yet."""
    exercise_id = db.execute(
        sa.text("SELECT id FROM exercises WHERE slug = :slug"), {"slug": SLUG}
    ).scalar_one_or_none()
    if exercise_id is None:
        return None, []
    rows = db.execute(
        sa.text(
            "SELECT id, position, name FROM ladder_steps WHERE exercise_id = :id ORDER BY position"
        ),
        {"id": exercise_id},
    )
    return exercise_id, [(row[0], row[1], row[2]) for row in rows]


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
    for row_id, payload in db.execute(sa.text("SELECT id, payload FROM events")):
        named = _json(payload) or {}
        if isinstance(named, dict) and {named.get(key) for key in EVENT_KEYS} & ids:
            found.append(f"events {row_id}")
    return found


def upgrade() -> None:
    db = op.get_bind()
    _, steps = _ladder(db)
    names = [name for _, _, name in steps]
    if GONE not in names:
        return  # a fresh database, or one this already ran on
    if names[-2:] != [EIGHT, GONE]:
        raise RuntimeError(f"{SLUG}: expected the ladder to end {[EIGHT, GONE]}, not {names}")
    gone_id = steps[-1][0]
    used = _in_use(db, {gone_id})
    if used:
        raise RuntimeError(
            f"{SLUG} {GONE!r} is in use ({', '.join(used)}); "
            "moving it onto the dumbbell step needs Liam's OK first"
        )
    db.execute(sa.text("DELETE FROM ladder_steps WHERE id = :id"), {"id": gone_id})


def downgrade() -> None:
    db = op.get_bind()
    exercise_id, steps = _ladder(db)
    if not steps or steps[-1][2] not in (DUMBBELLS, EIGHT):
        return  # a fresh database, or one already put back
    top_id, top, _ = steps[-1]
    db.execute(
        sa.text("UPDATE ladder_steps SET name = :name WHERE id = :id"),
        {"name": EIGHT, "id": top_id},
    )
    db.execute(
        sa.text(
            "INSERT INTO ladder_steps (exercise_id, position, name, level, marks)"
            " VALUES (:exercise, :position, :name, :level, '[]')"
        ),
        {"exercise": exercise_id, "position": top + 1, "name": GONE, "level": GONE_LEVEL},
    )
