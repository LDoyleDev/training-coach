"""Everything stored about one person, as one zip (GDPR Art. 15 and 20; security review):
``data.json`` with every per-person table, plus the progress photos as JPEG files.

Secrets are left out (token hashes, passkey keys, challenges); everything else is theirs. The
shared plan's exercises and ladder steps are included by id, so the ids in the data can be read.
"""

import io
import json
import zipfile
from datetime import date, datetime, time
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Mapper, Session

from training_coach.db.models import (
    Event,
    Exercise,
    ExerciseState,
    FitnessTestDay,
    HabitCheck,
    LadderStep,
    Measurement,
    Passkey,
    PlanState,
    PlanVersion,
    ProgressPhoto,
    SessionProgress,
    SessionTemplate,
    SetLog,
    UserSettings,
    WebSession,
    Workout,
)

# Per-person tables, by the name they get in data.json.
TABLES: dict[str, type] = {
    "workouts": Workout,
    "sets": SetLog,
    "test_days": FitnessTestDay,
    "measurements": Measurement,
    "progress_photos": ProgressPhoto,
    "habit_checks": HabitCheck,
    "settings": UserSettings,
    "plan_state": PlanState,
    "exercise_state": ExerciseState,
    "session_progress": SessionProgress,
    "signed_in_browsers": WebSession,
    "passkeys": Passkey,
    "events": Event,
}
# Secrets, and every binary column (the photos go in as files).
SECRET = frozenset({"token_hash", "public_key", "credential_id", "jpeg", "token"})


def _value(value: Any) -> Any:
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    return value


def _rows(session: Session, model: type) -> list[dict[str, Any]]:
    mapper: Mapper[Any] = inspect(model)
    columns = [c.key for c in mapper.column_attrs if c.key not in SECRET]
    order = mapper.primary_key[0]
    found: list[Any] = list(session.scalars(select(model).order_by(order)))
    return [{key: _value(getattr(row, key)) for key in columns} for row in found]


def _reference(session: Session) -> dict[str, Any]:
    """The shared plan's names, so exercise, step, session and version ids can be read."""
    return {
        "exercises": {
            e.id: {"slug": e.slug, "name": e.name} for e in session.scalars(select(Exercise))
        },
        "ladder_steps": {s.id: s.name for s in session.scalars(select(LadderStep))},
        "sessions": {t.id: t.name for t in session.scalars(select(SessionTemplate))},
        "plan_versions": {v.id: v.name for v in session.scalars(select(PlanVersion))},
    }


def archive(session: Session, now: datetime) -> bytes:
    """The zip for the user ``session`` is bound to."""
    data = {
        "exported_at": now.isoformat(),
        "tables": {name: _rows(session, model) for name, model in TABLES.items()},
        "reference": _reference(session),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr("data.json", json.dumps(data, indent=2, ensure_ascii=False))
        for photo in session.scalars(select(ProgressPhoto).order_by(ProgressPhoto.id)):
            name = f"photos/{photo.local_date.isoformat()}-{photo.pose}-{photo.id}.jpg"
            zipped.writestr(name, photo.jpeg)
    return buffer.getvalue()
