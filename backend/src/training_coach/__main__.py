"""Entry point: ``training-coach [serve|seed]`` (or ``python -m training_coach``)."""

import argparse
import sys
import tomllib

import structlog
import uvicorn
from pydantic import ValidationError

from training_coach.api.app import create_app
from training_coach.config import get_settings
from training_coach.db.session import make_engine, make_session_factory, session_scope
from training_coach.logging import configure_logging
from training_coach.services.seed import SeedError, apply_seed, load_plan

log = structlog.get_logger(__name__)


def serve() -> None:
    settings = get_settings()
    uvicorn.run(
        create_app(settings),
        host="0.0.0.0",  # noqa: S104 - bound inside the container; only the tunnel reaches it
        port=8080,
        log_config=None,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


def seed() -> None:
    """Apply the plan. On failure, log ``seed.failed`` with the reason and exit 1 (ADR-0015)."""
    settings = get_settings()
    configure_logging(settings)
    engine = make_engine(settings.database_url)
    try:
        with session_scope(make_session_factory(engine)) as session:
            apply_seed(session, load_plan())
    except (SeedError, ValidationError, tomllib.TOMLDecodeError) as exc:
        log.error("seed.failed", reason=str(exc))
        raise SystemExit(1) from exc
    finally:
        engine.dispose()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="training-coach")
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=["serve", "seed"],
        help="serve: API + bot (default). seed: load the training plan (idempotent).",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    {"serve": serve, "seed": seed}[args.command]()


if __name__ == "__main__":
    main()
