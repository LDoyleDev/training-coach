"""Two people, one signed in: no signed-in read shows the other's data (multi-user plan, L2).

Each person gets marked rows of every kind. Signed in as one, every GET route behind ``owner``
is called (found from the app, so a new route is covered without anyone remembering it). The
other's marks must not appear, and the answers must not change when the other person and
everything of theirs is deleted. A route that binds the wrong user or reads unbound fails here.
"""

import io
import json
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

import pytest
import time_machine
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import Engine, delete, select

from tests.routes import api_routes
from training_coach.api.app import create_app
from training_coach.api.auth import owner
from training_coach.config import Settings
from training_coach.db.models import (
    AiComment,
    DailyCheck,
    Exercise,
    ExerciseState,
    FitnessTestDay,
    HabitCheck,
    HealthDay,
    HeartRateSample,
    ImportedWorkout,
    Measurement,
    Passkey,
    ProgressPhoto,
    ReadinessAnswers,
    SessionTemplate,
    SetLog,
    SleepSession,
    User,
    UserSettings,
    WebSession,
    Workout,
)
from training_coach.db.session import make_session_factory, session_scope
from training_coach.domain import readiness
from training_coach.domain.enums import Side, WorkoutStatus
from training_coach.domain.habits import Habit
from training_coach.services import auth, seed

ORIGIN = "https://coach.example.com"
NOW = datetime(2026, 10, 12, 10, tzinfo=UTC)  # a Monday


@dataclass(frozen=True)
class Marks:
    name: str  # in free text: session label, passkey name, AI comment, band source
    tenths: int  # a waist measurement
    steps: int
    protein_g: int
    day: date  # a done workout, a test day, a band workout

    @property
    def visible(self) -> list[str]:
        """What the web app shows of these rows somewhere."""
        return [self.name, f"{self.tenths / 10:.1f}", str(self.steps), self.day.isoformat()]


ALPHA = Marks("Alphacanary", 1234, 12345, 173, date(2026, 10, 6))
BRAVO = Marks("Bravocanary", 1087, 6789, 141, date(2026, 10, 8))


@dataclass(frozen=True)
class Ids:
    workout_id: int
    photo_id: int


def _give(engine: Engine, user: int, marks: Marks) -> Ids:
    """Rows of every per-person kind the web app reads, each carrying ``marks``."""
    night = datetime.combine(marks.day, time(22), UTC)
    woke = NOW - timedelta(hours=2)  # the band shows last night and today's steps
    with session_scope(make_session_factory(engine, user_id=user)) as s:
        template = s.scalars(select(SessionTemplate).order_by(SessionTemplate.position)).first()
        state = s.scalars(select(ExerciseState)).first()
        assert template is not None
        assert state is not None
        workout = Workout(local_date=marks.day, status=WorkoutStatus.DONE, template_id=template.id)
        workout.sets = [
            SetLog(
                exercise_id=state.exercise_id,
                ladder_step_id=state.ladder_step_id,
                set_no=1,
                side=Side.BOTH,
                value=8,
            )
        ]
        photo = ProgressPhoto(local_date=marks.day, pose="front", jpeg=marks.name.encode(), size=9)
        prefs = s.scalars(select(UserSettings)).one()
        prefs.protein_g = marks.protein_g
        s.add_all(
            [
                workout,
                photo,
                Measurement(local_date=marks.day, kind="waist", tenths=marks.tenths),
                HabitCheck(local_date=marks.day, habit=Habit.PROTEIN),
                FitnessTestDay(
                    local_date=marks.day,
                    day=1,
                    time_of_day="morning",
                    fed=True,
                    slept_well=True,
                    results=[],
                    token=marks.name.ljust(20, "x"),
                ),
                ReadinessAnswers(
                    version=readiness.VERSION,
                    answers={q.key: False for q in readiness.QUESTIONS},
                    answered_at=NOW,
                ),
                DailyCheck(
                    local_date=NOW.date(),
                    sleep="good",
                    soreness="none",
                    energy="high",
                    answered_at=NOW,
                ),
                HealthDay(local_date=NOW.date(), steps=marks.steps, resting_hr=51),
                HeartRateSample(at=NOW - timedelta(hours=1), bpm=77, low=70, high=84),
                SleepSession(
                    source=f"com.{marks.name}",
                    start_at=woke - timedelta(hours=8),
                    end_at=woke,
                    local_date=NOW.date(),
                    asleep_min=420,
                    awake_min=20,
                    light_min=200,
                    deep_min=100,
                    rem_min=120,
                ),
                ImportedWorkout(
                    source=f"com.{marks.name}",
                    start_at=night - timedelta(hours=12),
                    end_at=night - timedelta(hours=11),
                    local_date=marks.day,
                    exercise_type=56,
                    activity="run",
                    minutes=60,
                ),
                AiComment(week=date(2026, 10, 5), text=f"{marks.name} trained well."),
                Passkey(credential_id=marks.name, public_key=b"ab" * 16, name=marks.name),
                WebSession(
                    token_hash=marks.name.ljust(64, "0"),
                    label=marks.name,
                    expires_at=NOW + timedelta(days=1),
                ),
            ]
        )
        s.flush()
        return Ids(workout_id=workout.id, photo_id=photo.id)


# Path parameters of owner-only GET routes: always the OTHER person's row, which must 404.
OTHERS: dict[str, str] = {
    "/api/session/stretching/{workout_id}": "workout_id",
    "/api/photos/{photo_id}": "photo_id",
}
QUERIES: dict[str, dict[str, str]] = {
    "/api/session/stretching/{workout_id}": {"minutes": "10"},
    "/api/log/plan": {"day": datetime.now(UTC).date().isoformat(), "template_id": "1"},
}


def _readable(response: Response) -> bytes:
    """The body, with an export unpacked so the marks inside it are seen, less the export
    events that each export adds to the person's own data."""
    if response.headers.get("content-type") != "application/zip":
        return response.content
    with zipfile.ZipFile(io.BytesIO(response.content)) as zipped:
        data = json.loads(zipped.read("data.json"))
        events = data["tables"]["events"]
        data["tables"]["events"] = [e for e in events if e["kind"] != "account.exported"]
        photos = [name.encode() + zipped.read(name) for name in zipped.namelist()[1:]]
    return b"\n".join([json.dumps(data).encode(), *photos])


def _reads(app: FastAPI, client: TestClient, other: Ids) -> dict[str, tuple[int, bytes]]:
    answers: dict[str, tuple[int, bytes]] = {}
    for path, route in api_routes(app):
        calls = {dependency.call for dependency in route.dependant.dependencies}
        if "GET" not in (route.methods or set()) or owner not in calls:
            continue
        url = path
        if "{" in path:
            assert path in OTHERS, f"{path}: add its parameter to OTHERS"
            url = path.replace(f"{{{OTHERS[path]}}}", str(getattr(other, OTHERS[path])))
        response = client.get(url, params=QUERIES.get(path))
        answers[path] = (response.status_code, _readable(response))
    return answers


@pytest.fixture
def two(engine: Engine) -> Iterator[Engine]:
    """The owner (user 1) and a second person, both with the plan's starting rows."""
    with time_machine.travel(NOW, tick=False):
        with session_scope(make_session_factory(engine)) as s:
            s.add(User(id=2))
            s.flush()
            seed.apply_seed(s, seed.bundled_plan())
        yield engine


@pytest.mark.parametrize(("me", "other"), [(2, 1), (1, 2)], ids=["member", "owner"])
def test_signed_in_reads_show_only_my_own_data(two: Engine, me: int, other: int) -> None:
    mine, theirs = (ALPHA, BRAVO) if me == 1 else (BRAVO, ALPHA)
    with make_session_factory(two, user_id=me)() as bound:
        token = auth.create_link(bound, NOW)
        bound.commit()
    settings = Settings(environment="test", database_url=str(two.url), public_url=ORIGIN)
    app = create_app(settings)
    with TestClient(app, base_url=ORIGIN) as client:
        # Signed in before the passkeys exist: a start link only works until then.
        assert client.post("/api/auth/redeem", json={"token": token}).status_code == 204
        _give(two, me, mine)
        their_ids = _give(two, other, theirs)
        before = _reads(app, client, their_ids)
        with session_scope(make_session_factory(two)) as s:
            s.execute(delete(User).where(User.id == other))  # cascades to all of theirs
            assert s.get(Exercise, 1) is not None  # the shared plan stays
        after = _reads(app, client, their_ids)

    assert len(before) >= 30, sorted(before)
    for path in OTHERS:
        assert before[path][0] == 404, f"{path} answered with the other person's row"
    for path, (code, _) in before.items():
        assert code == 200 or path in OTHERS, f"{path}: {code}"
    everything = b"".join(body for _, body in before.values()).decode("utf-8", "replace")
    for mark in theirs.visible:
        leaks = [p for p, (_, b) in before.items() if mark.encode() in b]
        assert not leaks, f"the other person's {mark!r} shows in {leaks}"
    for mark in mine.visible:
        assert mark in everything, f"my own {mark!r} shows nowhere: the canary isn't reached"
    changed = sorted(p for p in before if before[p] != after[p])
    assert not changed, f"deleting the other person changed what I see: {changed}"
