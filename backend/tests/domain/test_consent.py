"""Consent per category (ADR-0090): the newest answer counts, and only a yes to today's wording
opens a category."""

from datetime import UTC, datetime

import pytest

from training_coach.domain.consent import VERSIONS, Answer, Category, Entry, is_open, latest

AT = datetime(2026, 11, 8, 9, tzinfo=UTC)
LATER = datetime(2026, 11, 9, 9, tzinfo=UTC)


def _entry(answer: Answer, at: datetime = AT, category: Category = Category.BODY) -> Entry:
    return Entry(category, answer, VERSIONS[category], at)


def test_the_last_answer_written_per_category_counts() -> None:
    given, withdrawn = _entry(Answer.GIVEN), _entry(Answer.WITHDRAWN, LATER)
    band = _entry(Answer.GIVEN, category=Category.BAND)
    assert latest([given, band, withdrawn]) == {Category.BODY: withdrawn, Category.BAND: band}


def test_a_withdrawal_written_later_wins_even_if_the_clock_stepped_back() -> None:
    given, withdrawn = _entry(Answer.GIVEN, LATER), _entry(Answer.WITHDRAWN, AT)
    assert latest([given, withdrawn])[Category.BODY] == withdrawn


@pytest.mark.parametrize(
    ("entry", "expected"),
    [
        (None, False),
        (_entry(Answer.GIVEN), True),
        (_entry(Answer.WITHDRAWN), False),
        (Entry(Category.BODY, Answer.GIVEN, VERSIONS[Category.BODY] - 1, AT), False),
    ],
    ids=["never asked", "given", "withdrawn", "given to older wording"],
)
def test_only_a_yes_to_the_current_wording_opens_a_category(
    entry: Entry | None, expected: bool
) -> None:
    assert is_open(entry) is expected


def test_every_category_has_a_wording_version() -> None:
    assert set(VERSIONS) == set(Category)
