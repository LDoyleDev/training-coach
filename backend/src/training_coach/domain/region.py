"""Where the app is offered: the EU and EEA only (ADR-0085). Pure logic, no I/O.

The country is Cloudflare's ``CF-IPCountry`` (ISO 3166-1 alpha-2), read by ``api.region``
only from a trusted proxy. Two of its codes aren't countries: ``XX`` (no data) and ``T1``
(Tor). Neither is listed, so both are refused like any country outside the list. The country
of residence a person gives must be on the same list.
"""

from datetime import datetime, timedelta

# The 27 EU countries (Greece is GR, not EL).
EU = frozenset(
    {
        "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE",
        "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE",
    }
)  # fmt: skip
EEA = frozenset({"IS", "LI", "NO"})
# EU territories with their own codes: Åland, French Guiana, Guadeloupe, Martinique, Réunion,
# Mayotte, Saint Martin.
TERRITORIES = frozenset({"AX", "GF", "GP", "MQ", "RE", "YT", "MF"})
ALLOWED = EU | EEA | TERRITORIES


def listed(country: str) -> bool:
    """Whether a country code is one the app serves."""
    return country.strip().upper() in ALLOWED


def admits(country: str | None) -> bool:
    """Whether a request from ``country`` may reach the web app. ``None`` means no country was
    given by a trusted proxy (local development, tests, a process on the Pi, a missing
    Cloudflare header): let through, so a missing header can never lock the owner out."""
    return country is None or listed(country)


# The bot and the MCP endpoint can't see where a person is (long polling; an AI app's servers),
# so they serve an account only this long after its last signed-in visit from the list.
AWAY_LIMIT = timedelta(days=30)
# The visit is written at most this often: SQLite is on an SD card.
SEEN_EVERY = timedelta(hours=1)


def serves_remotely(last_seen_in_europe: datetime, now: datetime) -> bool:
    """Whether the bot and the MCP endpoint still serve an account last seen in Europe then."""
    return now - last_seen_in_europe <= AWAY_LIMIT


def worth_writing(last_seen_in_europe: datetime, now: datetime) -> bool:
    """Whether a visit from the list should be written down, or one was just recorded."""
    return now - last_seen_in_europe >= SEEN_EVERY
