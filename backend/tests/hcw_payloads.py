"""Payloads as Health Connect Webhook sends them (ADR-0055), for tests.

Shapes follow the app's own reference, docs/webhook.md in
https://github.com/mcnaveen/health-connect-webhook (v1.9.22, checked 2026-10-11), and the code
that builds them (``SyncManager.buildJsonPayload``): ISO-8601 UTC times, AndroidX constants
as strings for exercise types and sleep stages, heart rate in 1-minute buckets (the default)
with ``avg``/``min``/``max`` and ``bpm`` equal to ``avg``, and a ``metadata`` object naming the
app that wrote each record. The values are made up: one night, one walk, a weigh-in.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

NOW = datetime(2026, 10, 11, 8, 0, tzinfo=UTC)  # 10:00 in Berlin
MI = {
    "data_origin": "com.mi.health",
    "recording_method": "automatically_recorded",
    "device": {"manufacturer": "Xiaomi", "model": "Smart Band 9", "type": 6},
}
SLEEP_START = datetime(2026, 10, 10, 21, 30, tzinfo=UTC)  # 23:30 Berlin
SLEEP_END = datetime(2026, 10, 11, 5, 0, tzinfo=UTC)  # 07:00 Berlin
WALK_START = datetime(2026, 10, 10, 15, 0, tzinfo=UTC)
WALK_END = WALK_START + timedelta(minutes=46)


def iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def bucket(
    at: datetime, avg: int, low: int | None = None, high: int | None = None
) -> dict[str, Any]:
    return {
        "time": iso(at),
        "avg": avg,
        "min": low if low is not None else avg - 2,
        "max": high if high is not None else avg + 3,
        "bpm": avg,
        "metadata": MI,
    }


def night_heart_rate() -> list[dict[str, Any]]:
    """A minute every minute of the night; the lowest average is 48, at 02:00 UTC."""
    found = []
    minutes = int((SLEEP_END - SLEEP_START).total_seconds() // 60)
    for n in range(minutes):
        at = SLEEP_START + timedelta(minutes=n)
        found.append(bucket(at, 48 if at == datetime(2026, 10, 11, 2, 0, tzinfo=UTC) else 55))
    return found


def walk_heart_rate(rates: list[int] | None = None) -> list[dict[str, Any]]:
    """46 minutes: 8 at 100 bpm, then 38 at 140 bpm (zone 2 for a resting 48 and max 190)."""
    rates = rates or [100] * 8 + [140] * 38
    return [bucket(WALK_START + timedelta(minutes=n), bpm) for n, bpm in enumerate(rates)]


def sleep() -> dict[str, Any]:
    stages = [
        (4, SLEEP_START, 120),  # light
        (5, SLEEP_START + timedelta(minutes=120), 90),  # deep
        (1, SLEEP_START + timedelta(minutes=210), 10),  # awake
        (6, SLEEP_START + timedelta(minutes=220), 100),  # REM
        (4, SLEEP_START + timedelta(minutes=320), 130),  # light
    ]
    return {
        "session_end_time": iso(SLEEP_END),
        "duration_seconds": int((SLEEP_END - SLEEP_START).total_seconds()),
        "stages": [
            {
                "stage": str(stage),
                "start_time": iso(start),
                "end_time": iso(start + timedelta(minutes=length)),
                "duration_seconds": length * 60,
            }
            for stage, start, length in stages
        ],
        "metadata": MI,
    }


def walk() -> dict[str, Any]:
    return {
        "type": "79",  # EXERCISE_TYPE_WALKING
        "start_time": iso(WALK_START),
        "end_time": iso(WALK_END),
        "duration_seconds": 46 * 60,
        "distance_meters": 4120.5,
        "steps": 5230,
        "metadata": MI,
    }


def full() -> dict[str, Any]:
    """A morning sync with every type we use, and one we don't (distance)."""
    return {
        "timestamp": iso(NOW),
        "app_version": "1.9.22",
        "steps": [
            # "Daily" resolution: one record per local day, the oldest clamped to the window.
            {
                "count": 6500,
                "start_time": "2026-10-09T08:00:00Z",
                "end_time": "2026-10-09T22:00:00Z",
            },
            {
                "count": 11234,
                "start_time": "2026-10-09T22:00:00Z",
                "end_time": "2026-10-10T22:00:00Z",
            },
            {"count": 812, "start_time": "2026-10-10T22:00:00Z", "end_time": iso(NOW)},
        ],
        "sleep": [sleep()],
        "heart_rate": walk_heart_rate() + night_heart_rate(),
        "exercise": [walk()],
        "weight": [
            {"kilograms": 81.46, "time": "2026-10-11T05:20:00Z", "metadata": MI},
            {"kilograms": 81.9, "time": "2026-10-11T07:40:00Z", "metadata": MI},
        ],
        "distance": [{"meters": 4120.5, "start_time": iso(WALK_START), "end_time": iso(WALK_END)}],
    }


PIXEL = {
    "data_origin": "com.google.android.apps.fitness",
    "recording_method": "automatically_recorded",
    "device": {"manufacturer": "Google", "model": "Pixel Watch", "type": 1},
}


def mock() -> dict[str, Any]:
    """What the app's Test button sends (``MockPayloadBuilder.build``), abbreviated: made-up
    records for yesterday from a Pixel Watch, and a top-level ``"test": true``."""
    yesterday = datetime(2026, 10, 10, tzinfo=UTC)

    def at(hours: int, minutes: int = 0) -> str:
        return iso(yesterday + timedelta(hours=hours, minutes=minutes))

    return {
        "timestamp": iso(NOW),
        "app_version": "1.9.22",
        "test": True,
        "steps": [
            {"count": 1240, "start_time": at(0), "end_time": at(6), "metadata": PIXEL},
            {"count": 8432, "start_time": at(0), "end_time": at(10, 30), "metadata": PIXEL},
        ],
        "heart_rate": [
            {"bpm": 62, "time": at(6, 5), "metadata": PIXEL},
            {"bpm": 155, "time": at(8, 50), "metadata": PIXEL},
        ],
        "resting_heart_rate": [
            {"bpm": 58, "time": at(6), "metadata": PIXEL},
            {"bpm": 57, "time": iso(yesterday - timedelta(hours=18)), "metadata": PIXEL},
        ],
        "weight": [{"kilograms": 75.4, "time": iso(NOW - timedelta(hours=1)), "metadata": PIXEL}],
    }


# From v1.9.23 (docs/webhook.md, "Edits and deletions" and "Record metadata", checked
# 2026-10-22): each record's metadata carries its Health Connect ``id`` and
# ``last_modified_time``, an edited record comes again with the same id, ``deleted`` lists
# ``{type, id}`` per record removed since the last sync, and ``timezone`` names the zone the
# times are written in: new installs write the phone's local time with its offset.
NIGHT_ID = "3f1c2b9e-7d4a-4e1b-9c61-5a2f0e8d7b10"
WALK_ID = "a8d0c4e2-1b3f-4c5d-8e7f-90a1b2c3d4e5"


def identified(record: dict[str, Any], record_id: str, modified: datetime = NOW) -> dict[str, Any]:
    meta = {**record.get("metadata", MI), "id": record_id, "last_modified_time": iso(modified)}
    return {**record, "metadata": meta}


def local(moment: datetime) -> str:
    """A time as v1.9.25 writes it by default: Berlin wall-clock time with its offset."""
    return moment.astimezone(ZoneInfo("Europe/Berlin")).isoformat()


def changes(**arrays: list[dict[str, Any]]) -> dict[str, Any]:
    """A default sync from v1.9.25, with the given arrays (``deleted`` among them)."""
    return {"timestamp": local(NOW), "app_version": "1.9.25", "timezone": "Europe/Berlin", **arrays}
