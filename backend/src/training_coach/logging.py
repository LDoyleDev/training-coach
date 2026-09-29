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
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s")
    # httpx logs full request URLs, which contain the Telegram bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
