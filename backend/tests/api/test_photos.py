"""/api/photos (2-B, #143): progress photos, owner-only, cleaned and never logged."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from structlog.testing import capture_logs

from training_coach.api.app import create_app
from training_coach.config import Settings
from training_coach.db.models import ProgressPhoto, User
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain.photos import MAX_BYTES
from training_coach.domain.queue import local_date
from training_coach.services import auth
from training_coach.services.users import OWNER

ORIGIN = "https://coach.example.com"
JPEG = {"Content-Type": "image/jpeg"}


def segment(marker: int, body: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(body) + 2).to_bytes(2, "big") + body


GPS = b"GPS 52.5200N 13.4050E"
CLEAN = (
    bytes([0xFF, 0xD8])
    + segment(0xE0, b"JFIF\x00\x01\x01")
    + segment(0xDB, bytes(65))
    + segment(0xDA, b"\x01\x01\x00\x00\x3f\x00")
    + b"\x12\x34"
    + bytes([0xFF, 0xD9])
)
WITH_GPS = CLEAN[:2] + segment(0xE1, b"Exif\x00\x00" + GPS) + CLEAN[2:]


@pytest.fixture
def signed_in(engine: Engine) -> Iterator[TestClient]:
    with make_session_factory(engine, user_id=OWNER)() as bound:
        token = auth.create_link(bound, datetime.now(UTC))
        bound.commit()
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as client:
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        yield client


def _today() -> str:
    return local_date(datetime.now(UTC), Settings().tz).isoformat()


def test_a_photo_is_stored_without_its_location_and_served_privately(
    signed_in: TestClient,
) -> None:
    saved = signed_in.put(f"/api/photos/{_today()}/front", content=WITH_GPS, headers=JPEG)
    assert saved.status_code == 200
    photo_id = saved.json()["id"]
    picture = signed_in.get(f"/api/photos/{photo_id}")
    assert picture.status_code == 200
    assert picture.content == CLEAN
    assert GPS not in picture.content
    assert picture.headers["content-type"] == "image/jpeg"
    assert picture.headers["cache-control"] == "private, no-store"
    assert signed_in.get("/api/photos").json() == [
        {"id": photo_id, "on": _today(), "pose": "front", "size": len(CLEAN)}
    ]


def test_the_same_day_and_pose_is_replaced_and_poses_are_ordered(signed_in: TestClient) -> None:
    today = _today()
    first = signed_in.put(f"/api/photos/{today}/side", content=CLEAN, headers=JPEG).json()["id"]
    signed_in.put(f"/api/photos/{today}/front", content=CLEAN, headers=JPEG)
    again = signed_in.put(f"/api/photos/{today}/side", content=WITH_GPS, headers=JPEG).json()
    assert again["id"] == first
    assert [p["pose"] for p in signed_in.get("/api/photos").json()] == ["front", "side"]


def test_a_photo_can_be_deleted(signed_in: TestClient) -> None:
    photo_id = signed_in.put(f"/api/photos/{_today()}/back", content=CLEAN, headers=JPEG).json()[
        "id"
    ]
    assert signed_in.delete(f"/api/photos/{photo_id}").status_code == 204
    assert signed_in.delete(f"/api/photos/{photo_id}").status_code == 404
    assert signed_in.get(f"/api/photos/{photo_id}").status_code == 404
    assert signed_in.get("/api/photos").json() == []


@pytest.mark.parametrize(
    ("on", "content", "headers", "status"),
    [
        ("today", b"\x89PNG\r\n\x1a\n", JPEG, 422),
        ("today", CLEAN, {"Content-Type": "image/png"}, 415),
        ("today", bytes(MAX_BYTES + 1), JPEG, 413),
        ("future", CLEAN, JPEG, 422),
        ("long-ago", CLEAN, JPEG, 422),
    ],
    ids=["not-jpeg", "wrong-type", "too-large", "future", "long-ago"],
)
def test_what_cant_be_stored_is_refused(
    signed_in: TestClient, on: str, content: bytes, headers: dict[str, str], status: int
) -> None:
    today = datetime.fromisoformat(_today()).date()
    day = {"today": today, "future": today + timedelta(days=1)}.get(on, today - timedelta(30))
    answer = signed_in.put(f"/api/photos/{day.isoformat()}/front", content=content, headers=headers)
    assert answer.status_code == status
    assert signed_in.get("/api/photos").json() == []


def test_someone_elses_photo_is_not_found(signed_in: TestClient, engine: Engine) -> None:
    with session_scope(make_session_factory(engine)) as shared:
        shared.add(User(id=2))
    with session_scope(make_session_factory(engine, user_id=2)) as other:
        row = ProgressPhoto(
            local_date=datetime.fromisoformat(_today()).date(), pose="front", jpeg=CLEAN, size=1
        )
        other.add(row)
        other.flush()
        theirs = row.id
    assert signed_in.get(f"/api/photos/{theirs}").status_code == 404
    assert signed_in.delete(f"/api/photos/{theirs}").status_code == 404
    assert signed_in.get("/api/photos").json() == []


def test_photos_never_reach_the_logs(signed_in: TestClient) -> None:
    with capture_logs() as logs:
        saved = signed_in.put(f"/api/photos/{_today()}/front", content=WITH_GPS, headers=JPEG)
        signed_in.get(f"/api/photos/{saved.json()['id']}")
    text = repr(logs)
    assert "GPS" not in text
    assert "JFIF" not in text


def test_photos_need_a_signed_in_browser(engine: Engine) -> None:
    settings = Settings(environment="test", database_url=str(engine.url), public_url=ORIGIN)
    with TestClient(create_app(settings), base_url=ORIGIN) as stranger:
        assert stranger.get("/api/photos").status_code == 401
        assert stranger.get("/api/photos/1").status_code == 401
        assert stranger.delete("/api/photos/1").status_code == 401
        put = stranger.put("/api/photos/2026-10-10/front", content=CLEAN, headers=JPEG)
        assert put.status_code == 401
