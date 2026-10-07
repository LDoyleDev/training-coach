"""Entry point: ``training-coach [serve|seed|openapi|backup]`` (or ``python -m training_coach``)."""

import argparse
import json
import sys
import tomllib
from datetime import UTC, datetime

import structlog
import uvicorn
from pydantic import ValidationError

from training_coach.api.app import create_app
from training_coach.config import Settings, get_settings
from training_coach.db.session import make_engine, make_session_factory, session_scope
from training_coach.logging import configure_logging
from training_coach.services import backup as backups
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
    except Exception as exc:  # unexpected: keep the traceback in the log
        log.exception("seed.failed", reason=f"{type(exc).__name__}: {exc}")
        raise SystemExit(1) from exc
    finally:
        engine.dispose()


def backup() -> None:
    """A manual backup next to the nightly ones, e.g. before a deploy with a migration. It is
    never pruned; delete it by hand once it is no longer needed."""
    settings = get_settings()
    configure_logging(settings)
    source = backups.database_path(settings.database_url)
    if source is None:
        log.error("backup.failed", reason="the database is not a SQLite file")
        raise SystemExit(1)
    try:
        path = backups.create(
            source, source.parent / "backups", backups.manual_name(datetime.now(UTC))
        )
    except backups.BackupError as exc:
        log.error("backup.failed", reason=str(exc))
        raise SystemExit(1) from exc
    log.info("backup.created", file=str(path), bytes=path.stat().st_size)


def openapi() -> None:
    """Print the API schema as JSON. The dashboard's TypeScript types are generated from it
    (ADR-0020). Settings come from the class defaults alone, never from `.env` or `TC_`
    variables, so the output depends only on the code."""
    schema = create_app(Settings.model_construct(environment="test")).openapi()
    # The release version changes on every release PR; the types do not depend on it.
    schema["info"]["version"] = "0.0.0"
    sys.stdout.write(json.dumps(schema, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="training-coach")
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=["serve", "seed", "openapi", "backup"],
        help="serve: API + bot (default). seed: load the training plan (idempotent). "
        "openapi: print the API schema. backup: copy the database to data/backups/ now.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    commands = {"serve": serve, "seed": seed, "openapi": openapi, "backup": backup}
    commands[args.command]()


if __name__ == "__main__":
    main()
