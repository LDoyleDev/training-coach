"""The read-only Pi helper (scripts/pi-read.sh) blanks secret columns by name. These tests keep
its pattern in step with the models, so a new secret or binary column can't slip through, and
hold its query to reads that can't take the app down (review of 2026-10-24)."""

import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest
from sqlalchemy import Engine, LargeBinary

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


def _run(tmp_path: Path, query: str, db: Path | None = None) -> subprocess.CompletedProcess[str]:
    db = db or tmp_path / "coach.db"
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
        [sys.executable, str(script), query, uri],
        capture_output=True,
        encoding="utf-8",  # as in the container; Windows' default can't print an emoji
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=False,
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


PLANTED = ("SECRET-INGEST", "SECRET-SESSION", "SECRET-LOGIN", "SECRET-OAUTH", "SECRET-CODE")


def _planted(engine: Engine) -> Path:
    """The real schema with a secret in each kind of secret column."""
    path = Path(str(engine.url.database))
    inserts = [
        "INSERT INTO ingest_keys(user_id, key_hash, created_at) VALUES (1, ?, '2026')",
        "INSERT INTO web_sessions(user_id, token_hash, label, created_at, last_seen_at, "
        "expires_at) VALUES (1, ?, 'Firefox', '2026', '2026', '2027')",
        "INSERT INTO login_links(user_id, token_hash, created_at, expires_at, purpose) "
        "VALUES (1, ?, '2026', '2027', 'start')",
        "INSERT INTO ai_connections(user_id, groq_key, key_ends, enabled, share_body, "
        "share_readiness, updated_at) VALUES (1, CAST(? AS BLOB), 'abcd', 1, 0, 0, '2026')",
        "INSERT INTO passkey_challenges(handle_hash, challenge, purpose, expires_at) "
        "VALUES (?, X'00', 'sign_in', '2027')",
    ]
    with sqlite3.connect(path) as conn:
        for insert, secret in zip(inserts, PLANTED, strict=True):
            conn.execute(insert, (secret,))
    return path


@pytest.mark.parametrize(
    "query",
    [
        "SELECT key_hash AS harmless FROM ingest_keys",
        "SELECT (SELECT token_hash FROM web_sessions) AS x",
        "SELECT substr(token_hash, 1, 50), trim(token_hash), upper(token_hash) FROM login_links",
        "SELECT CAST(groq_key AS TEXT), printf('%s', groq_key) FROM ai_connections",
        "SELECT name FROM sqlite_master UNION ALL SELECT key_hash FROM ingest_keys",
        "WITH t AS (SELECT * FROM web_sessions) SELECT * FROM t",
        "SELECT group_concat(handle_hash) FROM passkey_challenges",
        "SELECT * FROM ingest_keys a JOIN web_sessions b USING (user_id)",
        "SELECT json_extract(json_array_length('[]'), '$'), max(token_hash) FROM login_links",
        "SELECT count(*) FROM ingest_keys WHERE key_hash = 'SECRET-INGEST'",
        "SELECT * FROM dbstat",  # Debian's sqlite has it; no row content in it
    ],
)
def test_no_planted_secret_comes_back(tmp_path: Path, engine: Engine, query: str) -> None:
    done = _run(tmp_path, query, _planted(engine))
    assert not any(secret in done.stdout for secret in PLANTED), done.stdout
    if "count(*)" in query:
        assert done.stdout.splitlines()[1] == "0"  # no oracle through WHERE either


@pytest.mark.parametrize(
    "query",
    [
        "WITH x AS (SELECT 1) REPLACE INTO ingest_keys(id, user_id, key_hash, created_at) "
        "VALUES (1, 1, 'x', 'y')",
        "SELECT * FROM pragma_journal_mode",
        "PRAGMA query_only = 0",
        "PRAGMA writable_schema = 1",
        "SELECT * FROM pragma_database_list",
        "SELECT hex(key_hash) FROM ingest_keys",
        # The memory limits can't be lifted from inside the query.
        "PRAGMA hard_heap_limit = 0",
        "SELECT * FROM pragma_hard_heap_limit",
        "PRAGMA temp_store = FILE",
    ],
)
def test_the_real_schema_refuses_more_than_a_read(
    tmp_path: Path, engine: Engine, query: str
) -> None:
    db = _planted(engine)
    assert _run(tmp_path, query, db).returncode != 0
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT key_hash FROM ingest_keys").fetchone() == (PLANTED[0],)


def test_a_sort_too_big_for_its_memory_fails_and_not_the_app(tmp_path: Path) -> None:
    """A sort used to spill to /tmp, a tmpfs counted against the app container's 512 MB, and the
    kernel killed the app before the 20 s limit. Now it runs out of its own budget first."""
    started = time.monotonic()
    done = _run(
        tmp_path,
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) "
        "SELECT x, printf('%99999d', x) FROM c ORDER BY 2 DESC",
    )
    assert done.returncode != 0
    assert "memory" in done.stderr, done.stderr
    assert time.monotonic() - started < 15  # the memory cap stopped it, not the time limit


@pytest.mark.parametrize(
    "query",
    [
        # One row of 50 values of 1 MB each (2000 of them built ~2 GB).
        "SELECT " + ",".join(f"printf('%999999d', {i})" for i in range(50)),
        # 500 rows of 1 MB each.
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c LIMIT 500) "
        "SELECT printf('%999999d', x) FROM c",
    ],
    ids=["one-wide-row", "many-rows"],
)
def test_a_result_is_capped_in_total_not_just_per_value(tmp_path: Path, query: str) -> None:
    done = _run(tmp_path, query)
    assert done.returncode != 0
    assert len(done.stdout) <= 4_000_000
    assert " MB" in done.stderr, done.stderr


def test_the_output_cap_counts_bytes_not_characters(tmp_path: Path) -> None:
    """Counted in characters, 4-byte ones let 15 MB through the 4 MB cap (review of
    2026-10-24)."""
    done = _run(
        tmp_path,
        "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c LIMIT 500) "
        "SELECT replace(printf('%240000d', x), ' ', '\U0001f600') FROM c",
    )
    assert done.returncode != 0
    assert 0 < len(done.stdout.encode()) <= 4_000_000
    assert " MB" in done.stderr, done.stderr


def test_a_result_has_at_most_100_columns(tmp_path: Path) -> None:
    assert _run(tmp_path, "SELECT " + ",".join(["1"] * 100)).returncode == 0
    done = _run(tmp_path, "SELECT " + ",".join(["1"] * 101))
    assert done.returncode != 0
    assert "too many columns" in done.stderr, done.stderr


def test_every_table_fits_in_the_column_cap(tmp_path: Path, engine: Engine) -> None:
    widest = max(models.Base.metadata.tables.values(), key=lambda table: len(table.columns))
    query = f"SELECT * FROM {widest.name}"  # noqa: S608 - a table name from our own models
    done = _run(tmp_path, query, Path(str(engine.url.database)))
    assert done.returncode == 0, done.stderr


def _logs(tmp_path: Path, docker_script: str, command: str) -> subprocess.CompletedProcess[str]:
    """Runs the helper's `logs` with a stub standing in for `docker compose logs`."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("no bash")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    docker = bin_dir / "docker"
    docker.write_text("#!/bin/sh\n" + docker_script)
    docker.chmod(0o755)
    env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    env |= {"TC_REPO_DIR": str(tmp_path), "SSH_ORIGINAL_COMMAND": command}
    return subprocess.run(  # noqa: S603 - our own script, fixed arguments
        [bash, str(SCRIPT)], env=env, capture_output=True, text=True, check=False
    )


def test_logs_with_no_match_say_so(tmp_path: Path) -> None:
    """grep finding nothing used to end the script (pipefail) with exit 1 and not a word."""
    lines = "echo 'GET /healthz 200'\necho 'band.import 3 rows'\n"
    found = _logs(tmp_path, lines, "logs 2h BAND.import")
    assert (found.returncode, found.stdout) == (0, "band.import 3 rows\n"), found.stderr
    for command in ("logs 2h nothing-like-this", "logs 2h healthz"):
        done = _logs(tmp_path, lines, command)
        assert done.returncode == 0, done.stderr
        assert "no matching lines" in done.stdout


@pytest.mark.parametrize("command", ["logs 2h", "logs 2h band"])
def test_logs_say_when_docker_fails(tmp_path: Path, command: str) -> None:
    """Docker's error went into the filters and the script exited 1 without a word (#317)."""
    failing = "echo 'Cannot connect to the Docker daemon' >&2\nexit 1\n"
    done = _logs(tmp_path, failing, command)
    assert done.returncode == 1
    assert "docker compose logs failed: Cannot connect to the Docker daemon" in done.stderr
    assert "no matching lines" not in done.stdout
