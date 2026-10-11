"""The read-only tools behind /mcp (ADR-0047 C1): the sections they add to the summary."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from training_coach.db.models import DailyCheck
from training_coach.services import ai_summary, mcp_tools
from training_coach.services.ai_summary import GUIDE_URL

TODAY = date(2026, 10, 11)


def test_readiness_includes_the_daily_checks_of_the_period(session: Session) -> None:
    for days, sleep in ((1, "poor"), (40, "good")):
        session.add(
            DailyCheck(
                local_date=TODAY - timedelta(days=days),
                sleep=sleep,
                soreness="a_lot",
                energy="low",
                answered_at=datetime.now(UTC),
            )
        )
    session.flush()
    text = ai_summary.readiness(session, TODAY - timedelta(weeks=4))
    assert "2026-10-10: sleep poor, soreness a lot, energy low" in text
    assert "sleep good" not in text  # older than the period
    assert "Readiness answers" in text


def test_no_daily_checks_says_so(session: Session) -> None:
    assert "None in this period." in ai_summary.readiness(session, TODAY)


def test_an_unknown_exercise_is_none(session: Session) -> None:
    assert ai_summary.exercise(session, "no-such-thing", None) is None


def test_the_guide_falls_back_to_its_address(monkeypatch: pytest.MonkeyPatch) -> None:
    mcp_tools.guide.cache_clear()
    monkeypatch.setattr(mcp_tools, "__file__", str(Path("/nowhere/at/all.py")))
    try:
        assert mcp_tools.guide() == f"Read the guide at {GUIDE_URL} (version 1)."
    finally:
        mcp_tools.guide.cache_clear()
