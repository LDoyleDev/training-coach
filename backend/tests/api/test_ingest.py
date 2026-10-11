"""Band data from the phone (ADR-0055): the ingest secret on Account, and the public route the
Health Connect Webhook app posts to."""

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from structlog.testing import capture_logs

from tests import hcw_payloads as hcw
from tests.api.test_erase import ORIGIN
from tests.api.test_erase import alerts as alerts  # shared fixtures
from tests.api.test_erase import signed_in as signed_in
from tests.api.test_export import _export
from training_coach.api import ingest
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import (
    HealthDay,
    HeartRateSample,
    ImportedWorkout,
    IngestKey,
    SleepSession,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services.users import OWNER

PATH = "/api/ingest/health-connect"


@pytest.fixture
def phone(engine: Engine) -> Iterator[TestClient]:
    """The phone: no cookies, no Origin."""
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        yield client


def _secret(signed_in: TestClient) -> str:
    made = signed_in.post("/api/account/ingest")
    assert made.status_code == 200
    secret: str = made.json()["secret"]
    return secret


def _post(phone: TestClient, secret: str, body: object = None) -> httpx.Response:
    content = json.dumps(hcw.full() if body is None else body)
    with time_machine.travel(hcw.NOW, tick=False):
        return phone.post(PATH, content=content, headers={"Authorization": f"Bearer {secret}"})


def test_a_secret_is_shown_once_and_kept_hashed(
    signed_in: TestClient, engine: Engine, alerts: list[str]
) -> None:
    assert signed_in.get("/api/account/ingest").json() == {
        "exists": False,
        "created_at": None,
        "last_used_at": None,
        "url": f"{ORIGIN}{PATH}",
    }
    made = signed_in.post("/api/account/ingest").json()
    assert made["secret"].startswith("tci_")
    assert len(made["secret"]) > 40
    assert made["exists"] is True
    status = signed_in.get("/api/account/ingest").json()
    assert "secret" not in status
    assert status["exists"] is True
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        (row,) = mine.scalars(select(IngestKey))
        assert len(row.key_hash) == 64
        assert made["secret"] not in row.key_hash
    assert alerts == ["A new band import secret was made."]


def test_making_a_secret_needs_a_recent_sign_in(signed_in: TestClient) -> None:
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        assert signed_in.post("/api/account/ingest").status_code == 403


def test_a_payload_is_stored_for_the_secrets_owner(
    signed_in: TestClient, phone: TestClient, engine: Engine
) -> None:
    secret = _secret(signed_in)
    with capture_logs() as logs:
        answer = _post(phone, secret)
    assert answer.status_code == 200
    assert answer.json() == {
        "taken": {"steps": 3, "sleep": 1, "heart_rate": 496, "exercise": 1, "weight": 2},
        "skipped": {},
    }
    assert "set-cookie" not in answer.headers
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert len(list(mine.scalars(select(SleepSession)))) == 1
    (line,) = [entry for entry in logs if entry["event"] == "ingest.stored"]
    assert line["heart_rate"] == 496
    # Counts only: no value, no time from the payload reaches the log.
    flat = json.dumps(logs, default=str)
    for value in ("81.46", "2026-10-11T05:00", "com.mi.health"):
        assert value not in flat
    assert signed_in.get("/api/account/ingest").json()["last_used_at"] is not None


def test_a_new_secret_replaces_the_old_one(signed_in: TestClient, phone: TestClient) -> None:
    old = _secret(signed_in)
    new = _secret(signed_in)
    assert _post(phone, old).status_code == 401
    assert _post(phone, new).status_code == 200


def test_a_removed_secret_stops_imports(
    signed_in: TestClient, phone: TestClient, alerts: list[str]
) -> None:
    secret = _secret(signed_in)
    assert signed_in.delete("/api/account/ingest").status_code == 204
    assert signed_in.delete("/api/account/ingest").status_code == 404
    assert _post(phone, secret).status_code == 401
    assert alerts[-1] == "The band import secret was removed."


@pytest.mark.parametrize(
    "header",
    [
        None,
        "Bearer",
        "Basic dGNpXzpzZWNyZXQ=",
        "Bearer tci_" + "ab" * 16,  # the right shape, nobody's
        "Bearer " + "ab" * 16,  # not ours at all
    ],
)
def test_without_a_known_secret_nothing_is_read(phone: TestClient, header: str | None) -> None:
    headers = {"Authorization": header} if header is not None else {}
    assert phone.post(PATH, json=hcw.full(), headers=headers).status_code == 401


def test_a_session_cookie_doesnt_stand_in_for_the_secret(signed_in: TestClient) -> None:
    assert signed_in.post(PATH, json=hcw.full()).status_code == 401


def test_guessing_secrets_is_cut_off(phone: TestClient) -> None:
    wrong = {"Authorization": "Bearer tci_" + "ab" * 16}
    for _ in range(ingest.MAX_FAILURES):
        assert phone.post(PATH, json={}, headers=wrong).status_code == 401
    assert phone.post(PATH, json={}, headers=wrong).status_code == 429


def test_too_many_calls_are_refused(phone: TestClient) -> None:
    limiter = ingest.Limiter()
    for n in range(ingest.MAX_CALLS):
        assert limiter.allow("a", float(n))
    assert not limiter.allow("a", 100.0)
    assert limiter.allow("b", 100.0)  # someone else
    assert limiter.allow("a", ingest.WINDOW + 1)  # the oldest call has aged out


def test_the_limiter_forgets_everyone_rather_than_grow() -> None:
    limiter = ingest.Limiter()
    for n in range(ingest.MAX_ADDRESSES + 2):
        limiter.allow(str(n), 0.0)
    assert len(limiter.calls) <= ingest.MAX_ADDRESSES + 1


def test_bodies_past_the_cap_are_refused(signed_in: TestClient, phone: TestClient) -> None:
    secret = _secret(signed_in)
    big = {"heart_rate": [], "padding": "x" * (ingest.MAX_BYTES + 1)}
    assert _post(phone, secret, big).status_code == 413


@pytest.mark.parametrize("content", ["not json", "[1, 2]", "\xff"])
def test_anything_but_a_json_object_is_refused(
    signed_in: TestClient, phone: TestClient, content: str
) -> None:
    secret = _secret(signed_in)
    answer = phone.post(
        PATH, content=content.encode("latin-1"), headers={"Authorization": f"Bearer {secret}"}
    )
    assert answer.status_code == 422


def test_bad_records_are_skipped_and_the_rest_kept(
    signed_in: TestClient, phone: TestClient
) -> None:
    secret = _secret(signed_in)
    body = {"timestamp": hcw.iso(hcw.NOW), "app_version": "1.9.22", "sleep": [hcw.sleep(), {}]}
    answer = _post(phone, secret, body)
    assert answer.json() == {"taken": {"sleep": 1}, "skipped": {"sleep": 1}}


def test_band_data_is_exported_and_erased(
    signed_in: TestClient, phone: TestClient, engine: Engine
) -> None:
    _post(phone, _secret(signed_in))
    tables = _export(signed_in)["tables"]
    assert len(tables["sleep_sessions"]) == 1
    assert len(tables["imported_workouts"]) == 1
    assert len(tables["heart_rate_samples"]) == 496
    assert "2026-10-11" in {d["local_date"] for d in tables["health_days"]}
    (key,) = tables["band_import_secret"]
    assert "key_hash" not in key
    assert signed_in.post("/api/account/erase", json={"confirm": "erase"}).status_code == 204
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        for model in (SleepSession, IngestKey, HeartRateSample, HealthDay, ImportedWorkout):
            assert mine.scalar(select(model.id).limit(1)) is None, model.__name__
