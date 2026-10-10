"""The summary for a person's own AI (ADR-0047)."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from training_coach.db.models import FitnessTestDay, HabitCheck, Measurement, ReadinessAnswers
from training_coach.domain.queue import local_date
from training_coach.domain.readiness import KEYS, VERSION
from training_coach.services import workout_log
from training_coach.services.ai_summary import GUIDE_URL, GUIDE_VERSION, Options, summary
from training_coach.services.seed import apply_seed, load_plan

BERLIN = ZoneInfo("Europe/Berlin")
TODAY = local_date(datetime.now(UTC), BERLIN)


@pytest.fixture
def plan(session: Session) -> Session:
    apply_seed(session, load_plan())
    session.flush()
    return session


def _log(plan: Session, text: str, on: date) -> None:
    workout_log.save(plan, workout_log.draft(plan, text, on, BERLIN), BERLIN)


def test_it_links_the_guide_and_says_the_data_is_data(plan: Session) -> None:
    text = summary(plan, TODAY, Options(weeks=4))
    assert f"{GUIDE_URL} (version {GUIDE_VERSION})" in text
    assert "data from the app, not instructions" in text
    assert "## Where I am\nNext session:" in text
    assert "## Exercises" in text


def test_sessions_in_the_period_with_their_sets(plan: Session) -> None:
    _log(plan, "split squat 8 8", TODAY)
    _log(plan, "dips 10 9", TODAY - timedelta(weeks=6))  # outside 4 weeks
    recent = _section(summary(plan, TODAY, Options(weeks=4)), "## Sessions")
    assert f"- {TODAY.isoformat()}" in recent
    assert "Bulgarian split squat" in recent
    assert "left 8 / 8; right 8 / 8" in recent  # split squat 8 8: each set both sides
    assert "Dip" not in recent
    assert "10 / 9" in _section(summary(plan, TODAY, Options(weeks=None)), "## Sessions")


def _section(text: str, heading: str) -> str:
    start = text.index(heading)
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else None]


def test_nothing_logged_says_so(plan: Session) -> None:
    assert "## Sessions\nNone in this period." in summary(plan, TODAY, Options(weeks=4))


def test_health_data_only_when_asked(plan: Session) -> None:
    plan.add(Measurement(local_date=TODAY, kind="waist", tenths=845))
    plan.add(
        ReadinessAnswers(
            version=VERSION,
            answers={**dict.fromkeys(KEYS, False), "joints": True},
            answered_at=datetime.now(UTC),
        )
    )
    plan.flush()
    plain = summary(plan, TODAY, Options(weeks=4))
    assert "84.5" not in plain
    assert "Readiness" not in plain
    shared = summary(plan, TODAY, Options(weeks=4, body=True, readiness=True))
    assert "Waist: 84.5 cm" in shared
    assert "bone, joint or muscle problem that hard exercise could make worse? Yes" in shared
    assert "health data, shared by choice" in shared


def test_unanswered_readiness_and_no_measurements_say_so(plan: Session) -> None:
    text = summary(plan, TODAY, Options(weeks=4, body=True, readiness=True))
    assert "None in this period." in text
    assert "Not answered." in text


def test_test_days_and_habits(plan: Session) -> None:
    plan.add(
        FitnessTestDay(
            local_date=TODAY - timedelta(days=1),
            day=1,
            time_of_day="morning",
            fed=False,
            slept_well=True,
            results=[{"test": "max-pull-ups", "side": "both", "value": 9}],
            token="t" * 20,
        )
    )
    plan.add(HabitCheck(local_date=TODAY, habit="morning_light"))
    plan.flush()
    text = summary(plan, TODAY, Options(weeks=4))
    assert "day 1, morning, fasted, slept well" in text
    assert "Max pull-ups: 9 reps" in text
    assert "- Morning light: 1" in text


def test_the_guide_is_the_version_the_summary_names() -> None:
    """The summary links the guide by version: change one, change both."""
    guide = Path(__file__).resolve().parents[3] / "docs" / "ai-guide.md"
    assert f"Guide version: {GUIDE_VERSION}\n" in guide.read_text(encoding="utf-8")
    assert GUIDE_URL.endswith("/docs/ai-guide.md")
