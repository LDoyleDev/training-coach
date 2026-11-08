import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from training_coach.domain.readiness import DUE_NOTE, HARD_NOTE, RENEW, VERSION, due, note

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
QUESTIONS_TS = Path(__file__).resolve().parents[3] / "frontend/src/readiness/questions.ts"


def test_answered_this_year_with_these_questions_isnt_due() -> None:
    assert not due(VERSION, NOW - RENEW + timedelta(seconds=1), NOW)


@pytest.mark.parametrize(
    ("version", "answered"),
    [
        (None, None),  # never answered
        (VERSION, NOW - RENEW),  # a year ago
        (VERSION - 1, NOW),  # the questions changed since (ADR-0046's seven)
    ],
)
def test_answers_that_no_longer_count_are_due_again(
    version: int | None, answered: datetime | None
) -> None:
    assert due(version, answered, NOW)


def test_only_a_hard_day_has_a_note_and_it_never_names_an_answer() -> None:
    assert note(is_due=True, hard=False) is None
    assert note(is_due=False, hard=False) is None
    assert note(is_due=True, hard=True) == DUE_NOTE
    assert note(is_due=False, hard=True) == HARD_NOTE
    for text in (DUE_NOTE, HARD_NOTE):  # ADR-0085's words
        assert not re.search(r"cleared|safe for you|risk|screening|clearance", text, re.I)


def test_the_web_asks_this_version_of_the_questions() -> None:
    """The questions live in the browser; bumping them there must bump VERSION here, or
    nobody is asked the new ones."""
    source = QUESTIONS_TS.read_text(encoding="utf-8")
    found = re.search(r"export const VERSION = (\d+)", source)
    assert found is not None
    assert int(found.group(1)) == VERSION
    assert len(re.findall(r"\bkey: '", source)) == 10  # the ten questions
