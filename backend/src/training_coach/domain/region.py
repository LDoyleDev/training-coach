"""Where the app is offered: the EU and EEA only (ADR-0085). Pure logic, no I/O.

The country is Cloudflare's ``CF-IPCountry`` (ISO 3166-1 alpha-2), read by ``api.region``
only from a trusted proxy. Two of its codes aren't countries: ``XX`` (no data) and ``T1``
(Tor). Neither is listed, so both are refused like any country outside the list.
"""

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
