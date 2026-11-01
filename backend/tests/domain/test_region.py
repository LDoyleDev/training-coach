from datetime import UTC, datetime, timedelta

import pytest

from training_coach.domain.region import (
    ALLOWED,
    admits,
    listed,
    serves_remotely,
    worth_writing,
)

SEEN = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def test_the_list_is_the_eu_the_eea_and_the_eu_territories() -> None:
    assert len(ALLOWED) == 37  # 27 + IS LI NO + AX GF GP MQ RE YT MF (ADR-0085)
    assert {"DE", "GR", "HU", "NO", "IS", "LI", "AX", "MF"} <= ALLOWED
    assert not {"EL", "EU", "GB", "CH", "US", "RU"} & ALLOWED


@pytest.mark.parametrize("country", ["DE", "de", " fr ", "NO", "RE"])
def test_listed_countries_are_admitted(country: str) -> None:
    assert listed(country)
    assert admits(country)


@pytest.mark.parametrize("country", ["US", "GB", "CH", "EU", "XX", "T1", ""])
def test_everyone_else_is_refused_including_unknown_and_tor(country: str) -> None:
    assert not listed(country)
    assert not admits(country)


def test_no_country_at_all_is_let_through() -> None:
    assert admits(None)


def test_the_bot_and_mcp_serve_for_30_days_after_a_visit_from_europe() -> None:
    assert serves_remotely(SEEN, SEEN)
    assert serves_remotely(SEEN, SEEN + timedelta(days=30))
    assert not serves_remotely(SEEN, SEEN + timedelta(days=30, seconds=1))


def test_a_visit_is_written_at_most_once_an_hour() -> None:
    assert not worth_writing(SEEN, SEEN + timedelta(minutes=59))
    assert worth_writing(SEEN, SEEN + timedelta(hours=1))
