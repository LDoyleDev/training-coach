"""The read-only Pi helper (scripts/pi-read.sh) blanks secret columns by name. These tests keep
its pattern in step with the models, so a new secret or binary column can't slip through."""

import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
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


def _query_script() -> str:
    found = re.search(
        r"^read -r -d '' QUERY_PY <<'PY' \|\| true\n(.*?)^PY$", SCRIPT.read_text(), re.M | re.S
    )
    assert found is not None, "the QUERY_PY block moved: update this test"
    return found.group(1)


def _run(tmp_path: Path, query: str) -> subprocess.CompletedProcess[str]:
    db = tmp_path / "coach.db"
    if not db.exists():
        with sqlite3.connect(db) as conn:
            conn.execute(
                "CREATE TABLE ingest_keys (id INTEGER, secret_hash TEXT, last_used_at TEXT)"
            )
            conn.execute("INSERT INTO ingest_keys VALUES (1, 'HASH', '2026-10-19')")
    script = tmp_path / "query.py"
    script.write_text(_query_script())
    uri = f"file:{db.as_posix()}?mode=ro"
    return subprocess.run(  # noqa: S603 - our own script and interpreter, fixed arguments
        [sys.executable, str(script), query, uri], capture_output=True, text=True, check=False
    )


def test_a_select_reads_with_secret_columns_blank(tmp_path: Path) -> None:
    done = _run(tmp_path, "SELECT * FROM ingest_keys")
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == ["id\tsecret_hash\tlast_used_at", "1\t\t2026-10-19"]


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM ingest_keys",
        "WITH x AS (SELECT 1) DELETE FROM ingest_keys",
        "SELECT 1; DELETE FROM ingest_keys",
        "PRAGMA journal_mode = WAL",
        "SELECT zeroblob(2000000000)",  # one call the time limit can't stop (review of #292)
        "SELECT load_extension('x')",
    ],
)
def test_anything_but_a_plain_read_is_refused(tmp_path: Path, query: str) -> None:
    assert _run(tmp_path, query).returncode != 0
    assert _run(tmp_path, "SELECT secret_hash FROM ingest_keys").stdout.splitlines()[1] == ""
    with sqlite3.connect(tmp_path / "coach.db") as conn:
        assert conn.execute("SELECT secret_hash FROM ingest_keys").fetchone() == ("HASH",)
