"""Entry point: ``training-coach [serve|seed|openapi|backup|notify|rotate-secrets]`` (or
``python -m training_coach``)."""

import argparse
import asyncio
import contextlib
import json
import os
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
from training_coach.services import ai_key
from training_coach.services import backup as backups
from training_coach.services.secret_box import SecretBox
from training_coach.services.seed import SeedError, apply_seed, load_plan

log = structlog.get_logger(__name__)


def serve() -> None:
    # The database, its WAL and the backups hold personal data: group-readable at most, so
    # the backup pull can read them (ADR-0024) and other users on the Pi can't.
    os.umask(0o027)
    settings = get_settings()
    uvicorn.run(
        create_app(settings),
        host="0.0.0.0",  # noqa: S104 - bound inside the container; only the tunnel reaches it
        port=8080,
        log_config=None,
        # The client address is the tunnel's; the visitor's comes only from CF-Connecting-IP,
        # believed only from TC_TRUSTED_PROXIES (api/passkeys.py). X-Forwarded-For is never
        # trusted: a visitor can set it (security review, 2026-10-10).
        proxy_headers=False,
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


NOTIFY_LENGTH = 1000  # one Telegram message, well under its limit


def notify(text: str = "") -> None:
    """Send ``text`` to the owner on Telegram: how jobs outside the app (a failed deploy or
    off-site backup, ``training-coach-alert@.service``) tell Liam. Exits 1 if it can't."""
    settings = get_settings()
    configure_logging(settings)
    message = text.strip()[:NOTIFY_LENGTH]
    if not message:
        log.error("notify.failed", reason="nothing to send")
        raise SystemExit(1)
    if settings.telegram_bot_token is None or settings.telegram_allowed_user_id is None:
        log.error("notify.failed", reason="the bot isn't configured")
        raise SystemExit(1)
    from telegram import Bot  # only here: the other commands don't need the bot
    from telegram.error import TelegramError

    from training_coach.bot.app import send_with_retry

    async def send() -> bool:
        assert settings.telegram_bot_token is not None  # noqa: S101 - checked above
        assert settings.telegram_allowed_user_id is not None  # noqa: S101 - checked above
        # No `async with`: its initialize() makes a request of its own that a network blip
        # would fail outside the retries. send_message needs none of it (review of #168).
        bot = Bot(settings.telegram_bot_token.get_secret_value())
        try:
            return await send_with_retry(bot, settings.telegram_allowed_user_id, message)
        except TelegramError as exc:  # anything the retries don't absorb is a failed alert
            log.error("notify.failed", reason=type(exc).__name__)
            return False
        finally:
            with contextlib.suppress(TelegramError):
                await bot.shutdown()

    if not asyncio.run(send()):
        log.error("notify.failed", reason="telegram didn't take it")
        raise SystemExit(1)
    log.info("notify.sent")


def rotate_secrets() -> None:
    """Re-seal every stored secret (people's AI keys) with the newest TC_SECRETS_KEY, so an
    older key can be removed (ADR-0047, docs/runbooks/rotate-secrets.md)."""
    settings = get_settings()
    configure_logging(settings)
    if settings.secrets_key is None:
        sys.exit("TC_SECRETS_KEY is not set")
    engine = make_engine(settings.database_url)
    try:
        with session_scope(make_session_factory(engine)) as session:
            done, lost = ai_key.rotate_all(session, SecretBox(settings.secrets_key))
    finally:
        engine.dispose()
    log.info("secrets.rotated", resealed=done, unreadable=lost)
    sys.stdout.write(f"Re-sealed {done} key(s) with the newest secrets key; {lost} unreadable.\n")


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
        choices=["serve", "seed", "openapi", "backup", "notify", "rotate-secrets"],
        help="serve: API + bot (default). seed: load the training plan (idempotent). "
        "openapi: print the API schema. backup: copy the database to data/backups/ now. "
        "notify TEXT: send TEXT to the owner on Telegram. "
        "rotate-secrets: re-seal stored keys with the newest TC_SECRETS_KEY.",
    )
    parser.add_argument("text", nargs="?", default="", help="the message, for notify")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    if args.command == "notify":
        notify(args.text)
        return
    commands = {
        "serve": serve,
        "seed": seed,
        "openapi": openapi,
        "backup": backup,
        "rotate-secrets": rotate_secrets,
    }
    commands[args.command]()


if __name__ == "__main__":
    main()
