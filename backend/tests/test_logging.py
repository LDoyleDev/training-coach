import io
import sys

import pytest
import structlog

from training_coach.config import Settings
from training_coach.logging import configure_logging


def test_a_logger_writes_to_stdout_as_it_is_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """#39: a logger first used under one stdout kept writing to it after it was replaced (and,
    under pytest, closed). Outside production every log line goes to the current stdout."""
    first, second = io.StringIO(), io.StringIO()
    monkeypatch.setattr(sys, "stdout", first)
    configure_logging(Settings(environment="test"))
    log = structlog.get_logger("probe")
    log.info("first.event")

    monkeypatch.setattr(sys, "stdout", second)
    log.info("second.event")

    assert "first.event" in first.getvalue()
    assert "second.event" in second.getvalue()
    assert "second.event" not in first.getvalue()


def test_production_still_caches_loggers() -> None:
    configure_logging(Settings(environment="production"))
    try:
        assert structlog.get_config()["cache_logger_on_first_use"] is True
    finally:
        configure_logging(Settings(environment="test"))
