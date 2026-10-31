"""ladders down (ADR-0083): easier steps below the bottom of twelve ladders, the squat back

ADR-0083 extends a ladder downward where the easier step is the same movement, so a person's
progress and history stay on one exercise. The seed matches steps by position and only appends,
so this moves the steps: every listed exercise's steps go up by the number of new ones, keeping
their ids, and the new steps are inserted below them with the names, levels and marks plan.toml
gives them (the seed writes their cues on its next run, as it does for every step). The retired
``goblet-squat`` comes back as "Squat" with the sit-to-stand steps below its goblet steps, so it
keeps its slug and history (ADR-0083, option A).

Steps are found by exercise slug and name, as ids differ between databases. Every ladder must be
exactly as the previous release's seed left it (``LADDERS``, positions 0, 1, 2...; the pull-up's
top may still be "Vest or backpack, 5 kg", as b7e1c3d5f9a2 leaves it until the seed renames it),
and the squat's exercise row must still be the retired "Goblet squat": if anything differs it stops
before any write and the whole migration rolls back. An exercise not in the database yet (a
fresh one) is skipped; the seed then writes its whole ladder.

What refers to a step, and why only positions move:

- ``ladder_steps.position``: the only stored position. Parked out of the way first (+10000, as
  the seed does for sessions), so the unique (exercise, position) never sees two steps on one.
- By step id, so unchanged and still pointing at the same step: ``exercise_state.ladder_step_id``
  (each person's level), ``set_logs.ladder_step_id``, ``session_progress.steps`` (levels chosen
  for today) and ``session_progress.sets[].step_id`` (kept sets of a session in progress),
  ``replaced_workouts.data.sets`` (kept for /undo), and the ``events`` payloads that name a step
  (``progress.moved_up``, ``progress.level_set``, ``progress.not_yet``, ``progress.top_noted``).
- By exercise id: session items (``template_items``); no position there.
- By step name: needs, cues, questions, levels, marks and loads in plan.toml, and the figures in
  ``frontend/src/figures/steps.ts``.
- ``start`` in plan.toml (where a new person begins) is not stored: it moves up by the same
  number in plan.toml, so it names the same step as before.
- Step numbers worked out when shown (Progress, the bot's /progress "n/m", the AI summary's
  "step n of m", the share card's blocks) renumber: the same step gets a higher number.

Downgrade deletes the new steps and moves the old ones back down, and puts the squat back as the
retired "Goblet squat". It refuses, changing nothing, if anything uses a new step: a logged set,
someone's level, a session in progress, a replaced workout or an event. Once anyone has used a
new step, restore the pre-deploy backup instead (docs/runbooks/deploy.md, Rollback).

Revision ID: 5ebed72122f7
Revises: d4f9b2a6e8c1
Create Date: 2026-10-31 14:00:00.000000

"""

import json
from collections.abc import Sequence
from typing import Any, NamedTuple

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5ebed72122f7"
down_revision: str | Sequence[str] | None = "d4f9b2a6e8c1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARK = 10_000  # past any real position


class New(NamedTuple):
    """A step added below a ladder: its name, level (1-6) and marks, as plan.toml has them."""

    name: str
    level: int
    marks: tuple[str, ...] = ()


# slug -> (the ladder as the previous release's seed left it, the new steps below it), both
# easiest first. plan.toml's ladder is the new steps then the old ones (a test holds it).
LADDERS: dict[str, tuple[tuple[str, ...], tuple[New, ...]]] = {
    "goblet-squat": (
        ("8 kg, 3 s lowering", "1.5-rep squats, 8 kg", "Heavier kettlebell"),
        (
            New("Raised seat, hands push off", 1),
            New("Sit to stand, hands push off", 1),
            New("Sit to stand, hands on thighs", 1),
            New("Sit to stand, arms crossed", 2),
            New("A lower seat, arms crossed", 2),
            New("To a chair, touch and go", 3),
            New("To a chair, holding a backpack", 3),
            New("Full depth", 4),
        ),
    ),
    "push-up": (
        ("Standard", "Feet elevated", "Deficit", "Archer"),
        (
            New("Hands on a wall", 1),
            New("Hands on a counter", 1),
            New("Hands on a table", 2),
            New("Hands on a chair seat against a wall", 2),
            New("On the knees", 3, ("floor", "kneeling")),
            New("Hands on a stair or low step", 3),
        ),
    ),
    "side-plank-hip-dip": (
        ("On the knees", "Straight legs", "Top leg raised", "Holding 8 kg on the hip"),
        (New("Side lean on a wall", 1), New("Forearm on a counter", 2)),
    ),
    "kb-row": (
        ("8 kg", "8 kg, 3 s lowering", "16 kg", "16 kg, 3 s lowering", "16 kg, pause at top"),
        (New("A bag, about 4 kg", 2),),
    ),
    "pull-up": (
        ("Slow negatives", "Strict pull-up", "Pause at top", "Vest or backpack"),
        (New("Feet on a chair", 3, ("hanging",)), New("Scapular pulls", 3, ("hanging",))),
    ),
    "calf-raise": (
        ("Bodyweight on a step", "Holding 8 kg", "8 kg, 2 s pause at top"),
        (New("Both legs, hands on a wall", 1), New("Both legs, on a step", 2)),
    ),
    "suitcase-carry": (
        ("8 kg", "16 kg", "Farmer carry, 16 kg + 8 kg, swap hands each set"),
        (
            New("A bag, 1-3 kg, standing at the counter", 1),
            New("A bag, 1-3 kg, walking along the counter", 2),
            New("A bag, 3-5 kg", 2),
        ),
    ),
    "kb-curl": (
        (
            "8 kg",
            "8 kg, slow tempo",
            "8 kg, 3 s lowering, pause at top",
            "16 kg, hammer grip",
            "16 kg, slow tempo",
        ),
        (New("Water bottles, about 1 kg", 1), New("A bag, 2-4 kg", 2)),
    ),
    "lateral-raise": (
        ("8 kg or water bottles", "Lean-away single-arm"),
        (New("Seated, water bottles", 1),),
    ),
    "bulgarian-split-squat": (
        (
            "Bodyweight, back foot on chair",
            "Goblet hold, 8 kg",
            "Goblet hold, 3 s lowering",
            "Goblet hold, 16 kg",
            "Goblet hold 16 kg, 3 s lowering",
            "Suitcase hold, 16 kg + 8 kg",
        ),
        (
            New("Holding a chair, short range", 2),
            New("Holding a chair, full range", 3),
            New("Back foot on a low step", 3, ("balance",)),
        ),
    ),
    "copenhagen-plank": (
        (
            "Knee on a chair",
            "Knee on a chair, 3 s lowering",
            "Ankle on a chair",
            "Ankle on a chair, 3 s lowering",
        ),
        (New("Knee on a chair, bottom foot helping", 3, ("floor",)),),
    ),
    "back-extension": (
        ("Floor superman", "Hips on bed edge, feet anchored", "Holding 8 kg at chest"),
        (New("Lying on a bed", 2),),
    ),
    "zone2": (
        ("Brisk walk / hike", "Easy jog / bike", "Easy jog with weight vest or backpack"),
        (New("Easy walk, short bouts are fine", 1),),
    ),
}
# The pull-up's top step as b7e1c3d5f9a2 leaves it, before the seed renames it in place: a
# database that runs both migrations in one upgrade has this name there.
PULL_UP_TOP = ("Vest or backpack, 5 kg", "Vest or backpack")
SQUAT = "goblet-squat"
SQUAT_BEFORE = "Goblet squat"  # retired
SQUAT_AFTER = "Squat"

_IDS = sa.bindparam("ids", expanding=True)
COUNTS = {
    "set_logs": "SELECT count(*) FROM set_logs WHERE ladder_step_id IN :ids",
    "exercise_state": "SELECT count(*) FROM exercise_state WHERE ladder_step_id IN :ids",
}
EVENT_KEYS = ("step_id", "from_step_id", "to_step_id")


def _ladder(db: sa.Connection, slug: str) -> tuple[int | None, list[tuple[int, int, str]]]:
    """The exercise's id and its (id, position, name) steps, easiest first; (None, []) when the
    exercise isn't in the database yet."""
    exercise_id = db.execute(
        sa.text("SELECT id FROM exercises WHERE slug = :slug"), {"slug": slug}
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


def _same(found: tuple[str, ...], old: tuple[str, ...]) -> bool:
    """Whether ``found`` is the ladder ``old``, allowing the pull-up's unrenamed top step."""
    if len(found) != len(old):
        return False
    return all(f == o or {f, o} == set(PULL_UP_TOP) for f, o in zip(found, old, strict=True))


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


def _move(db: sa.Connection, exercise_id: int, by: int) -> None:
    """Move an exercise's steps ``by`` positions, parking them first so no two share one."""
    move = "UPDATE ladder_steps SET position = position + :by WHERE exercise_id = :id"
    db.execute(sa.text(move), {"by": PARK, "id": exercise_id})
    db.execute(sa.text(move), {"by": by - PARK, "id": exercise_id})


def _squat(db: sa.Connection) -> tuple[str, bool] | None:
    row = db.execute(
        sa.text("SELECT name, retired FROM exercises WHERE slug = :slug"), {"slug": SQUAT}
    ).one_or_none()
    return None if row is None else (row[0], bool(row[1]))


def upgrade() -> None:
    db = op.get_bind()
    moving: dict[str, int] = {}
    wrong: list[str] = []
    for slug, (old, _new) in LADDERS.items():
        exercise_id, steps = _ladder(db, slug)
        if exercise_id is None or not steps:
            continue  # a fresh database: the seed writes the whole ladder
        names = tuple(name for _, _, name in steps)
        positions = [position for _, position, _ in steps]
        if not _same(names, old) or positions != list(range(len(old))):
            wrong.append(f"{slug}: expected {list(old)} at 0-{len(old) - 1}, found {list(names)}")
        moving[slug] = exercise_id
    squat = _squat(db)
    if squat is not None and squat != (SQUAT_BEFORE, True):
        wrong.append(f"{SQUAT}: expected the retired {SQUAT_BEFORE!r}, found {squat}")
    if wrong:
        raise RuntimeError(
            "the ladders are not as the previous release left them, so nothing was moved; "
            "check the live data before going on: " + "; ".join(wrong)
        )
    insert = sa.text(
        "INSERT INTO ladder_steps (exercise_id, position, name, level, marks)"
        " VALUES (:id, :position, :name, :level, :marks)"
    )
    for slug, exercise_id in moving.items():
        new = LADDERS[slug][1]
        _move(db, exercise_id, len(new))
        for position, step in enumerate(new):
            db.execute(
                insert,
                {"id": exercise_id, "position": position, "name": step.name}
                | {"level": step.level, "marks": json.dumps(list(step.marks))},
            )
    if squat is not None:
        db.execute(
            sa.text("UPDATE exercises SET name = :name, retired = 0 WHERE slug = :slug"),
            {"name": SQUAT_AFTER, "slug": SQUAT},
        )


def downgrade() -> None:
    db = op.get_bind()
    going: dict[str, tuple[int, list[int]]] = {}
    wrong: list[str] = []
    for slug, (old, new) in LADDERS.items():
        exercise_id, steps = _ladder(db, slug)
        names = tuple(name for _, _, name in steps)
        if exercise_id is None or not steps or _same(names[: len(old)], old):
            continue  # never seeded, or already as before
        below = tuple(step.name for step in new)
        above = names[len(below) : len(below) + len(old)]
        # Steps a later seed appended at the top stay, moved down with the rest.
        if names[: len(below)] != below or not _same(above, old):
            wrong.append(f"{slug}: expected {list(below + old)}, found {list(names)}")
            continue
        going[slug] = (exercise_id, [step_id for step_id, _, _ in steps[: len(new)]])
    if wrong:
        raise RuntimeError("the ladders are not as this migration left them: " + "; ".join(wrong))
    used = _in_use(db, {step_id for _, ids in going.values() for step_id in ids})
    if used:
        raise RuntimeError(
            f"the new steps are in use ({', '.join(used)}), so nothing was moved back; restore "
            "the pre-deploy backup instead (docs/runbooks/deploy.md, Rollback)"
        )
    for exercise_id, ids in going.values():
        db.execute(
            sa.text("DELETE FROM ladder_steps WHERE id IN :ids").bindparams(_IDS), {"ids": ids}
        )
        _move(db, exercise_id, -len(ids))
    if _squat(db) is not None:
        db.execute(
            sa.text("UPDATE exercises SET name = :name, retired = 1 WHERE slug = :slug"),
            {"name": SQUAT_BEFORE, "slug": SQUAT},
        )
