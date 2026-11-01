"""The read-only tools behind /mcp (ADR-0047 C1): the sections they add to the summary."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from training_coach.db.models import DailyCheck
from training_coach.domain.connections import Scope
from training_coach.services import ai_summary, mcp_tools, user_settings
from training_coach.services.ai_summary import GUIDE_URL, GUIDE_VERSION
from training_coach.services.seed import apply_seed, load_plan

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
        assert mcp_tools.guide() == f"Read the guide at {GUIDE_URL} (version {GUIDE_VERSION})."
    finally:
        mcp_tools.guide.cache_clear()


def test_no_read_tool_shows_the_talk_test_setting(session: Session) -> None:
    """ADR-0083 review: a preference stays between the person and the app; their AI never
    reads it."""
    user_settings.update(session, talk_test=True)
    session.flush()
    scopes = frozenset(s.value for s in Scope)
    arguments = {"get_exercise": {"slug": "pull-up"}}
    for tool in mcp_tools.TOOLS:
        if tool.name in (mcp_tools.PROPOSE, "get_guide"):
            continue
        try:
            text = mcp_tools.run(session, tool, arguments.get(tool.name, {}), scopes, TODAY)
        except mcp_tools.BadArgumentsError:  # no such exercise without a seeded plan
            continue
        assert "talk" not in text.lower(), tool.name


def test_no_read_tool_shows_what_the_person_avoids(session: Session) -> None:
    """ADR-0083: the five preferences stay between the person and the app, even where they lock
    a step the AI reads about (every pull-up step hangs)."""
    apply_seed(session, load_plan())
    user_settings.update(
        session,
        avoid_floor=True,
        avoid_kneeling=True,
        avoid_impact=True,
        avoid_hanging=True,
        avoid_knees=True,
    )
    session.flush()
    scopes = frozenset(s.value for s in Scope)
    arguments = {"get_exercise": {"slug": "pull-up"}}
    for tool in mcp_tools.TOOLS:
        if tool.name in (mcp_tools.PROPOSE, "get_guide"):
            continue
        text = mcp_tools.run(session, tool, arguments.get(tool.name, {}), scopes, TODAY).lower()
        for said in (*("chosen", "avoid", "keep me off", "no kneeling", "no jumping"),
                     *("no hanging", "easy on", "go easy", "knee bending")):  # fmt: skip
            assert said not in text, (tool.name, said)


def test_no_read_tool_shows_the_last_set_option(session: Session) -> None:
    """ADR-0084: the last-set option is a setting between the person and the app."""
    apply_seed(session, load_plan())
    user_settings.update(session, last_set_amrap=True)
    session.flush()
    scopes = frozenset(s.value for s in Scope)
    arguments = {"get_exercise": {"slug": "pull-up"}}
    for tool in mcp_tools.TOOLS:
        if tool.name in (mcp_tools.PROPOSE, "get_guide"):
            continue
        text = mcp_tools.run(session, tool, arguments.get(tool.name, {}), scopes, TODAY).lower()
        for said in ("last_set", "as many good reps", "as many as you can"):
            assert said not in text, (tool.name, said)
