"""The read-only Pi helper (scripts/pi-read.sh) blanks secret columns by name. These tests keep
its pattern in step with the models, so a new secret or binary column can't slip through."""

import re
from pathlib import Path

from sqlalchemy import LargeBinary

from training_coach.db import models

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pi-read.sh"
SECRETISH = re.compile(r"hash|secret|token|key|password|challenge|credential|cookie", re.I)


def _mask() -> re.Pattern[str]:
    found = re.search(r'^SECRET = re\.compile\(r"([^"]+)", re\.I\)$', SCRIPT.read_text(), re.M)
    assert found is not None, "the SECRET pattern moved: update this test"
    return re.compile(found.group(1), re.I)


def _columns() -> list[tuple[str, str, object]]:
    return [
        (table.name, column.name, column.type)
        for table in models.Base.metadata.tables.values()
        for column in table.columns
    ]


def test_every_binary_column_is_blanked() -> None:
    mask = _mask()
    binary = [(t, c) for t, c, kind in _columns() if isinstance(kind, LargeBinary)]
    assert binary  # photos, passkeys and challenges are stored as bytes
    assert [(t, c) for t, c in binary if not mask.search(c)] == []


def test_every_secret_looking_column_is_blanked() -> None:
    mask = _mask()
    assert [(t, c) for t, c, _ in _columns() if SECRETISH.search(c) and not mask.search(c)] == []


def test_the_encrypted_groq_key_is_blanked() -> None:
    assert _mask().search("groq_key")  # Fernet ciphertext is still a stored secret (review of #292)
