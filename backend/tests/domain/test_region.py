import pytest

from training_coach.domain.region import ALLOWED, admits, listed


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
