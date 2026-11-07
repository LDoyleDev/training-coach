"""The people who left (ADR-0088), listed outside the database so a restore can't bring them back.

Restoring a backup puts back a database from before someone left, and them with it. This list
is a file next to the database, not in it, so a restore doesn't roll it back; the off-site job
copies it each night (``scripts/offsite-backup.sh``), so it outlives the SD card too. An entry
holds the person's id, when they joined and when they left, nothing else. Ids can be used again
(SQLite hands out the highest id plus one, and a restore resets that), so a person still in the
database matches an entry only by id *and* join time: someone new on a left person's id is never
touched. An entry is dropped once no backup from before the leave can still exist.
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from training_coach.db.models import User

NAME = "left-users.json"
# Backups age out within 5 weeks (domain.backups, the off-site 35 days); a week more to be safe.
KEEP = timedelta(days=42)
FILE_MODE = 0o640  # like the backups: owner and the app group only


@dataclass(frozen=True)
class Left:
    user_id: int
    joined: datetime
    left: datetime


def path_for(database: Path) -> Path:
    """Where the list for ``database`` lives: beside it, outside ``backups/``."""
    return database.parent / NAME


def read(path: Path) -> list[Left]:
    if not path.exists():
        return []
    return [
        Left(int(e["id"]), datetime.fromisoformat(e["joined"]), datetime.fromisoformat(e["left"]))
        for e in json.loads(path.read_text(encoding="utf-8"))
    ]


def record(path: Path, user_id: int, joined: datetime, now: datetime) -> None:
    """Add someone who is leaving, and drop entries no backup can need any more. Written before
    their rows are deleted: a delete that then fails leaves them listed, never the other way."""
    kept = [e for e in read(path) if now - e.left < KEEP]
    _write(path, [*kept, Left(user_id, joined, now)])


def _write(path: Path, entries: list[Left]) -> None:
    text = json.dumps(
        [
            {"id": e.user_id, "joined": e.joined.isoformat(), "left": e.left.isoformat()}
            for e in entries
        ]
    )
    partial = path.with_name(path.name + ".partial")
    with partial.open("w", encoding="utf-8") as out:
        out.write(text)
        out.flush()
        os.fsync(out.fileno())  # on the disk before it replaces the old list
    partial.chmod(FILE_MODE)
    partial.replace(path)


def back(session: Session, entries: list[Left]) -> list[int]:
    """The ids of listed people who are in the database again, matched by id and join time.
    Run in an unbound session (``users`` is shared)."""
    if not entries:
        return []
    listed = {(e.user_id, e.joined) for e in entries}  # an id can have left more than once
    ids = {user for user, _ in listed}
    found = session.execute(select(User.id, User.created_at).where(User.id.in_(ids)))
    return sorted(user for user, created in found if (user, created) in listed)
