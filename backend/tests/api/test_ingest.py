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
from tests.alerts import capture
from tests.api.test_erase import ORIGIN
from tests.api.test_erase import alerts as alerts  # shared fixtures
from tests.api.test_erase import signed_in as signed_in
from tests.api.test_export import _export
from training_coach.api import ingest
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import (
    BandFeed,
    HealthDay,
    HeartRateSample,
    ImportedWorkout,
    IngestKey,
    Measurement,
    SleepSession,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.band_watch import Refusal
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
        "refused_at": None,
        "refused_reason": None,
        "app_version": None,
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


def test_a_sync_notes_each_daily_kind_it_took(
    signed_in: TestClient, phone: TestClient, engine: Engine
) -> None:
    body = {key: value for key, value in hcw.full().items() if key != "sleep"}
    _post(phone, _secret(signed_in), body)
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        noted = {row.feed: row.last_taken_at for row in mine.scalars(select(BandFeed))}
    assert noted == {"steps": hcw.NOW, "heart_rate": hcw.NOW}  # workouts and weight aren't watched


# ------------------------------------------- refused syncs, shown on Account (ADR-0055)


def _status(signed_in: TestClient) -> dict[str, object]:
    found: dict[str, object] = signed_in.get("/api/account/ingest").json()
    return found


def test_a_sync_too_large_is_noted_with_why(signed_in: TestClient, phone: TestClient) -> None:
    secret = _secret(signed_in)
    big = {"heart_rate": [], "padding": "x" * (ingest.MAX_BYTES + 1)}
    assert _post(phone, secret, big).status_code == 413
    status = _status(signed_in)
    assert (status["refused_at"], status["refused_reason"]) == ("2026-10-11T08:00:00Z", "too_large")
    assert status["last_used_at"] is None


@pytest.mark.parametrize("content", ["not json", "[1, 2]"], ids=["text", "array"])
def test_a_sync_not_a_json_object_is_noted(
    signed_in: TestClient, phone: TestClient, content: str
) -> None:
    secret = _secret(signed_in)
    with time_machine.travel(hcw.NOW, tick=False):
        phone.post(PATH, content=content, headers={"Authorization": f"Bearer {secret}"})
    assert _status(signed_in)["refused_reason"] == "not_json"


def test_a_stored_sync_after_a_refusal_clears_it(signed_in: TestClient, phone: TestClient) -> None:
    secret = _secret(signed_in)
    _post(phone, secret, {"timestamp": hcw.iso(hcw.NOW), "app_version": "1.9.22"})
    with time_machine.travel(hcw.NOW + timedelta(minutes=10), tick=False):
        phone.post(PATH, content="[]", headers={"Authorization": f"Bearer {secret}"})
    assert _status(signed_in)["refused_reason"] == "not_json"
    # Within the hour that would otherwise skip noting it: the first stored sync after a
    # refusal is always noted, so Account stops showing the refusal.
    with time_machine.travel(hcw.NOW + timedelta(minutes=20), tick=False):
        phone.post(PATH, json=hcw.full(), headers={"Authorization": f"Bearer {secret}"})
    status = _status(signed_in)
    assert (status["refused_at"], status["refused_reason"]) == (None, None)
    assert status["last_used_at"] == "2026-10-11T08:20:00Z"


def test_a_sync_whose_records_were_all_skipped_is_noted(
    signed_in: TestClient, phone: TestClient
) -> None:
    secret = _secret(signed_in)
    body = {"timestamp": hcw.iso(hcw.NOW), "app_version": "1.9.22", "sleep": [{}, {}]}
    assert _post(phone, secret, body).json() == {"taken": {}, "skipped": {"sleep": 2}}
    status = _status(signed_in)
    assert status["refused_reason"] == "skipped"
    assert status["last_used_at"] == status["refused_at"] == "2026-10-11T08:00:00Z"
    assert status["last_taken_at"] is None


def test_a_bad_deletion_alone_isnt_a_skipped_sync(signed_in: TestClient, phone: TestClient) -> None:
    # A malformed deleted entry drops no record, so it isn't "every record left out".
    secret = _secret(signed_in)
    answer = _post(phone, secret, hcw.changes(deleted=[{"type": "sleep"}]))
    assert answer.json() == {"taken": {}, "skipped": {"deleted": 1}}
    status = _status(signed_in)
    assert (status["refused_at"], status["refused_reason"]) == (None, None)
    assert status["last_used_at"] == "2026-10-11T08:00:00Z"


def test_a_sync_that_fails_to_store_is_noted(
    signed_in: TestClient, phone: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    secret = _secret(signed_in)

    def store(*args: object, **kwargs: object) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(health_import, "store", store)
    with pytest.raises(RuntimeError):
        _post(phone, secret)
    assert _status(signed_in)["refused_reason"] == "failed"


def test_refusals_are_written_at_most_hourly_unless_the_reason_changes(engine: Engine) -> None:
    bound = make_session_factory(engine, user_id=OWNER)
    with session_scope(bound) as mine:
        ingest_keys.make(mine, hcw.NOW - timedelta(days=1))
    steps = [
        (0, Refusal.TOO_LARGE, 0),
        (20, Refusal.TOO_LARGE, 0),  # same reason within the hour: not written
        (30, Refusal.NOT_JSON, 30),  # another reason: written
        (95, Refusal.NOT_JSON, 95),  # an hour on: written
    ]
    for minutes, reason, noted in steps:
        with session_scope(bound) as mine:
            ingest_keys.refused(mine, hcw.NOW + timedelta(minutes=minutes), reason)
            found = ingest_keys.status(mine)
        assert found.refused_at == hcw.NOW + timedelta(minutes=noted)
        assert found.refused_reason is reason


def test_the_apps_version_is_kept_and_a_new_secret_clears_it_all(
    signed_in: TestClient, phone: TestClient
) -> None:
    secret = _secret(signed_in)
    _post(phone, secret, hcw.changes())
    assert _status(signed_in)["app_version"] == "1.9.25"
    with time_machine.travel(hcw.NOW, tick=False):
        phone.post(PATH, content="[]", headers={"Authorization": f"Bearer {secret}"})
    _secret(signed_in)
    status = _status(signed_in)
    assert (status["app_version"], status["refused_reason"], status["last_used_at"]) == (
        None,
        None,
        None,
    )


def test_a_wrong_secret_notes_nothing(
    signed_in: TestClient, phone: TestClient, engine: Engine
) -> None:
    _secret(signed_in)
    assert _post(phone, "tci_" + "ab" * 16, [1]).status_code == 401
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        assert mine.scalars(select(IngestKey)).one().refused_at is None


def test_deletions_are_counted_in_the_answer(signed_in: TestClient, phone: TestClient) -> None:
    secret = _secret(signed_in)
    body = hcw.changes(
        exercise=[hcw.identified(hcw.walk(), hcw.WALK_ID)],
        deleted=[{"type": "sleep", "id": hcw.NIGHT_ID}, {"type": "heart_rate", "id": "x"}],
    )
    with capture_logs() as logs:
        answer = _post(phone, secret, body)
    assert answer.json() == {"taken": {"exercise": 1}, "skipped": {}, "deleted": {"sleep": 1}}
    (line,) = [entry for entry in logs if entry["event"] == "ingest.stored"]
    assert line["sleep_deleted"] == 1
    assert hcw.NIGHT_ID not in json.dumps(logs, default=str)


def _reader_sync() -> dict[str, object]:
    """A sync as the band reader sends it (android/.../Payload.kt, ADR-0070): one record per
    local day of steps and raw heart-rate samples, each naming the app that wrote it."""
    mi = {"data_origin": "com.mi.health"}
    return {
        "timestamp": hcw.iso(hcw.NOW),
        "app_version": "tc-reader/0.0.1",
        "steps": [
            {
                "count": 812,
                "start_time": "2026-10-10T22:00:00Z",
                "end_time": hcw.iso(hcw.NOW),
                "metadata": mi,
            }
        ],
        "heart_rate": [
            {"bpm": bpm, "time": f"2026-10-11T07:{at}Z", "metadata": mi}
            for bpm, at in ((60, "00:05"), (62, "00:25"), (64, "00:45"), (70, "01:10"))
        ],
    }


def test_the_readers_sync_is_taken_and_sending_it_again_changes_nothing(
    signed_in: TestClient, phone: TestClient, engine: Engine
) -> None:
    # The reader sends a sync again when a later post of it failed: that must be harmless.
    secret = _secret(signed_in)
    for _ in range(2):
        answer = _post(phone, secret, _reader_sync())
        assert answer.status_code == 200
        assert answer.json()["taken"] == {"steps": 1, "heart_rate": 4}
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        minutes = [
            (s.bpm, s.low, s.high)
            for s in mine.scalars(select(HeartRateSample).order_by(HeartRateSample.at))
        ]
        steps = mine.scalar(select(HealthDay.steps))
    assert minutes == [(62, 60, 64), (70, 70, 70)]
    assert steps == 812
    assert signed_in.get("/api/account/ingest").json()["app_version"] == "tc-reader/0.0.1"


# ------------------------------------- a stolen secret (security test, 2026-10-24)


def test_a_flood_of_workouts_in_one_post_stores_only_the_cap(
    signed_in: TestClient, phone: TestClient, engine: Engine
) -> None:
    most = health_import.MOST["exercise"]
    start = hcw.NOW - timedelta(days=1)
    walks = [
        {"type": "8", "start_time": hcw.iso(at), "end_time": hcw.iso(at)}
        for at in (start + timedelta(microseconds=n) for n in range(most + 50))
    ]
    answer = _post(phone, _secret(signed_in), {"exercise": walks})
    assert answer.json() == {"taken": {"exercise": most}, "skipped": {"exercise": 50}}
    assert _stored(engine)["ImportedWorkout"] == most


def test_one_secret_is_limited_whatever_the_address(
    signed_in: TestClient, phone: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    addresses = iter(range(100))
    monkeypatch.setattr(ingest, "_client", lambda request: f"10.0.0.{next(addresses)}")
    secret = _secret(signed_in)
    for _ in range(ingest.MAX_PER_SECRET):
        assert _post(phone, secret, {}).status_code == 200
    assert _post(phone, secret, {}).status_code == 429


def test_only_two_posts_are_parsed_at_once(signed_in: TestClient, phone: TestClient) -> None:
    # 5 MB of raw heart rate peaks near 60 MB parsed; parallel posts mustn't pass 512 MB.
    secret = _secret(signed_in)
    state = phone.app.state  # type: ignore[attr-defined]  # a FastAPI app
    state.ingest_parsing = ingest.MAX_PARSING
    answer = _post(phone, secret)
    assert (answer.status_code, answer.headers["retry-after"]) == (503, "60")
    state.ingest_parsing = ingest.MAX_PARSING - 1
    assert _post(phone, secret).status_code == 200
    assert state.ingest_parsing == ingest.MAX_PARSING - 1


def test_a_lone_surrogate_is_refused_and_noted(signed_in: TestClient, phone: TestClient) -> None:
    # It was a 500: SQLite can't store half a UTF-16 pair.
    secret = _secret(signed_in)
    escaped = [f"{chr(92)}u{unit:04x}" for unit in (0xD800, 0xD83D, 0xDE00)]  # JSON's escapes
    for version, code in ((escaped[0], 422), (escaped[1] + escaped[2], 200)):  # half, emoji
        content = f'{{"app_version": "{version}", "sleep": [{json.dumps(hcw.sleep())}]}}'
        with time_machine.travel(hcw.NOW, tick=False):
            answer = phone.post(
                PATH, content=content, headers={"Authorization": f"Bearer {secret}"}
            )
        assert answer.status_code == code
        if code == 422:
            assert _status(signed_in)["refused_reason"] == "not_json"


def test_the_apps_version_loses_control_and_bidi_characters(
    signed_in: TestClient, phone: TestClient
) -> None:
    secret = _secret(signed_in)
    _post(phone, secret, {"app_version": "1.9.25‮\x00​" + "A" * 40})
    assert _status(signed_in)["app_version"] == "1.9.25" + "A" * 26


def test_a_declared_length_past_the_cap_is_refused_before_reading(
    signed_in: TestClient, phone: TestClient
) -> None:
    secret = _secret(signed_in)
    headers = {"Authorization": f"Bearer {secret}", "Content-Length": str(ingest.MAX_BYTES + 1)}
    with time_machine.travel(hcw.NOW, tick=False):
        answer = phone.post(PATH, content=b"{}", headers=headers)
    assert answer.status_code == 413
    assert _status(signed_in)["refused_reason"] == "too_large"


def test_the_person_is_told_when_the_band_moves_their_max(
    signed_in: TestClient, phone: TestClient
) -> None:
    told = capture(phone)
    secret = _secret(signed_in)
    _post(phone, secret)  # an ordinary walk: nothing moves
    body = {"exercise": [hcw.walk()], "heart_rate": hcw.walk_heart_rate([140] * 16 + [230] * 30)}
    _post(phone, secret, body)
    assert told == [
        "Your band data moved the max heart rate your zones use from 190 to 210 bpm. If that"
        " doesn't look right, set your own max under Settings."
    ]
