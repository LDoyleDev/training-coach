"""GET /api/account/export: everything stored about the signed-in person, as a zip."""

import io
import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.api.test_photos import CLEAN, JPEG
from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import Measurement, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.queue import local_date
from training_coach.services import auth
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
