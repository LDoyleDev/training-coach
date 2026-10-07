"""Structured logging. JSON in production, readable console output in development."""

import logging
import sys

import structlog

from training_coach.config import Settings


def configure_logging(settings: Settings) -> None:
    level = getattr(logging, settings.log_level)
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if settings.environment == "production"
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        # No file argument: each logger writes to sys.stdout as it is when created. Caching
        # pins that stream for good, so it's for production only; in tests a logger first used
        # under one test's captured stdout kept writing to it after it closed (#39).
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=settings.environment == "production",
    )
    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s")
    # httpx logs full request URLs, which contain the Telegram bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
