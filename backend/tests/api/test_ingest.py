"""Band data from the phone (ADR-0055): the ingest secret on Account, and the public route the
Health Connect Webhook app posts to."""

import asyncio
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
    Measurement,
    SleepSession,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.services import health_import, ingest_keys
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
        "last_taken_at": None,
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
    status = signed_in.get("/api/account/ingest").json()
    assert status["last_used_at"] == status["last_taken_at"] == "2026-10-11T08:00:00Z"


def test_an_empty_sync_is_noted_but_isnt_data_arriving(
    signed_in: TestClient, phone: TestClient
) -> None:
    secret = _secret(signed_in)
    empty = {"timestamp": hcw.iso(hcw.NOW), "app_version": "1.9.22"}
    assert _post(phone, secret, empty).json() == {"taken": {}, "skipped": {}}
    status = signed_in.get("/api/account/ingest").json()
    assert status["last_used_at"] is not None
    assert status["last_taken_at"] is None


def test_a_refused_sync_isnt_noted(signed_in: TestClient, phone: TestClient) -> None:
    # Only a stored sync counts as one getting through: a sync refused forever is a gap.
    secret = _secret(signed_in)
    assert _post(phone, secret, [1, 2]).status_code == 422
    status = signed_in.get("/api/account/ingest").json()
    assert status["last_used_at"] is None


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


def test_the_limiter_doesnt_grow_without_bound() -> None:
    limiter = ingest.Limiter()
    for n in range(ingest.MAX_ADDRESSES + 2):
        limiter.allow(str(n), 0.0)
    assert len(limiter.calls) <= ingest.MAX_ADDRESSES
    assert len(limiter.failures) <= ingest.MAX_ADDRESSES


def test_many_addresses_dont_wipe_a_guessers_count(monkeypatch: pytest.MonkeyPatch) -> None:
    # Review of #224: a full table used to be cleared, resetting every wrong-secret count.
    monkeypatch.setattr(ingest, "MAX_ADDRESSES", 5)
    limiter = ingest.Limiter()
    for _ in range(ingest.MAX_FAILURES):
        assert limiter.allow("guesser", 0.0)
        limiter.failed("guesser", 0.0)
    for n in range(20):
        limiter.allow(f"other{n}", 1.0)
    assert not limiter.allow("guesser", 2.0)


def test_bodies_past_the_cap_are_refused(signed_in: TestClient, phone: TestClient) -> None:
    secret = _secret(signed_in)
    big = {"heart_rate": [], "padding": "x" * (ingest.MAX_BYTES + 1)}
    assert _post(phone, secret, big).status_code == 413


@pytest.mark.parametrize(
    "content", ["not json", "[1, 2]", "\xff", "[" * 60_000], ids=["text", "array", "bytes", "deep"]
)
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


def test_parsing_and_storing_run_off_the_event_loop(
    signed_in: TestClient, phone: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A first sync is megabytes of heart rate: it mustn't stall the bot and the web app."""
    secret = _secret(signed_in)
    real = health_import.store
    loops: list[bool] = []

    def store(*args: object, **kwargs: object) -> None:
        try:
            asyncio.get_running_loop()
            loops.append(True)
        except RuntimeError:  # a worker thread has no running loop
            loops.append(False)
        real(*args, **kwargs)  # type: ignore[arg-type]  # passes the real arguments on

    monkeypatch.setattr(health_import, "store", store)
    assert _post(phone, secret).status_code == 200
    assert loops == [False]


def _stored(engine: Engine) -> dict[str, int]:
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        found = {
            model.__name__: len(list(mine.scalars(select(model.id))))
            for model in (HealthDay, HeartRateSample, SleepSession, ImportedWorkout)
        }
        found["weight"] = len(list(mine.scalars(select(Measurement.id))))
    return found


def test_the_apps_test_button_stores_nothing(
    signed_in: TestClient, phone: TestClient, engine: Engine
) -> None:
    # Found on live data: the Test button's made-up records (16,864 steps, resting 58 and 57,
    # 75.4 kg) were stored as the band's.
    secret = _secret(signed_in)
    with capture_logs() as logs:
        answer = _post(phone, secret, hcw.mock())
    assert answer.status_code == 200
    assert answer.json() == {
        "test": True,
        "taken": {},
        "skipped": {},
        "note": "test received; nothing stored",
    }
    assert _stored(engine) == {
        "HealthDay": 0,
        "HeartRateSample": 0,
        "SleepSession": 0,
        "ImportedWorkout": 0,
        "weight": 0,
    }
    assert [entry["event"] for entry in logs if entry["event"].startswith("ingest.")] == [
        "ingest.test"
    ]
    # It proves the address and the secret work: a sync got through, but no data arrived.
    status = signed_in.get("/api/account/ingest").json()
    assert status["last_used_at"] == "2026-10-11T08:00:00Z"
    assert status["last_taken_at"] is None


def test_a_test_with_a_wrong_secret_is_refused(phone: TestClient) -> None:
    wrong = {"Authorization": "Bearer tci_" + "ab" * 16}
    assert phone.post(PATH, json=hcw.mock(), headers=wrong).status_code == 401


@pytest.mark.parametrize("flag", [False, None, "true", 1], ids=["false", "null", "text", "one"])
def test_only_test_true_is_a_test(
    signed_in: TestClient, phone: TestClient, engine: Engine, flag: object
) -> None:
    # Real syncs never send the flag; anything but a JSON true is stored as usual.
    body = {**hcw.mock(), "test": flag}
    answer = _post(phone, _secret(signed_in), body)
    assert answer.json() == {
        "taken": {"steps": 2, "heart_rate": 2, "resting_heart_rate": 2, "weight": 1},
        "skipped": {},
    }
    assert _stored(engine)["weight"] == 1


def test_a_test_doesnt_end_a_gap_already_told(
    signed_in: TestClient, phone: TestClient, engine: Engine
) -> None:
    secret = _secret(signed_in)
    told = hcw.NOW - timedelta(hours=2)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        row = mine.scalars(select(IngestKey)).one()
        row.last_taken_at, row.alerted_at = hcw.NOW - timedelta(days=2), told
    _post(phone, secret, hcw.mock())
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        row = mine.scalars(select(IngestKey)).one()
        assert row.last_taken_at == hcw.NOW - timedelta(days=2)
        assert row.alerted_at == told
        assert ingest_keys.watch(mine, hcw.NOW + timedelta(minutes=5)) is None  # not "back"
