"""GET /api/account/export: everything stored about the signed-in person, as a zip."""

import io
import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
import time_machine
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect

from tests.api.test_photos import CLEAN, JPEG
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Event, Measurement, Passkey, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import auth
from training_coach.services.export import TABLES, secret
from training_coach.services.seed import apply_seed, load_plan
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    with session_scope(make_session_factory(engine)) as shared:
        apply_seed(shared, load_plan())
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


@pytest.fixture
def alerts(signed_in: TestClient) -> list[str]:
    sent: list[str] = []

    async def notify(text: str) -> None:
        sent.append(text)

    signed_in.app.state.notify = notify  # type: ignore[attr-defined]  # a FastAPI app
    return sent


def _unzip(content: bytes) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(content))


def test_the_export_holds_my_data_and_photos_but_no_secrets(
    signed_in: TestClient, engine: Engine
) -> None:
    today = local_date(datetime.now(UTC), Settings().tz).isoformat()
    signed_in.put("/api/body", json={"values": {"bodyweight": 83.4}})
    signed_in.put(f"/api/photos/{today}/front", content=CLEAN, headers=JPEG)
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
    with session_scope(make_session_factory(engine, user_id=2)) as theirs:
        theirs.add(Measurement(local_date=date(2026, 10, 1), kind="waist", tenths=999))

    answer = signed_in.get("/api/account/export")
    assert answer.status_code == 200
    assert answer.headers["content-type"] == "application/zip"
    assert answer.headers["content-disposition"].startswith('attachment; filename="training-coach-')
    assert answer.headers["cache-control"] == "private, no-store"

    zipped = _unzip(answer.content)
    data = json.loads(zipped.read("data.json"))
    tables = data["tables"]
    assert [m["tenths"] for m in tables["measurements"]] == [834]  # mine only
    assert tables["signed_in_browsers"][0]["label"]
    assert all("token_hash" not in row for row in tables["signed_in_browsers"])
    assert all("jpeg" not in row for row in tables["progress_photos"])
    assert "Pull-up" in {e["name"] for e in data["reference"]["exercises"].values()}
    (photo,) = [n for n in zipped.namelist() if n.startswith("photos/")]
    assert photo.startswith(f"photos/{today}-front-")
    assert zipped.read(photo) == CLEAN


def test_the_export_needs_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/account/export").status_code == 401


def _export(client: TestClient) -> dict[str, Any]:
    answer = client.get("/api/account/export")
    assert answer.status_code == 200
    data: dict[str, Any] = json.loads(_unzip(answer.content).read("data.json"))
    return data


def test_no_secret_column_is_ever_exported(signed_in: TestClient, engine: Engine) -> None:
    """By rule, not by list: binary and *_hash columns and credential ids, in every table."""
    with session_scope(make_session_factory(engine, user_id=OWNER)) as mine:
        mine.add(Passkey(credential_id="cred", public_key=b"key", sign_count=0, name="Pixel"))
    tables = _export(signed_in)["tables"]
    for name, model in TABLES.items():
        hidden = {c.key for c in inspect(model).column_attrs if secret(c.columns[0])}
        for row in tables[name]:
            assert not hidden & set(row), name
            assert not any(key.endswith("_hash") for key in row), name
    (key,) = tables["passkeys"]
    assert key["name"] == "Pixel"
    assert "public_key" not in key
    assert "credential_id" not in key


def test_system_events_and_other_peoples_rows_stay_out(
    signed_in: TestClient, engine: Engine
) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(Event(kind="seed.applied", payload={}))  # a system event: no user
    kinds = {e["kind"] for e in _export(signed_in)["tables"]["events"]}
    assert "seed.applied" not in kinds


def test_an_export_needs_a_recent_sign_in_and_is_alerted(
    signed_in: TestClient, alerts: list[str], engine: Engine
) -> None:
    _export(signed_in)
    assert alerts == [
        "All your Training Coach data was downloaded. Not you? Sign that device out on the "
        "Account page, or send /recover."
    ]
    assert "account.exported" in {e["kind"] for e in _export(signed_in)["tables"]["events"]}
    with time_machine.travel(datetime.now(UTC) + timedelta(minutes=11)):
        assert signed_in.get("/api/account/export").status_code == 403
