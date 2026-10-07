"""FastAPI application. One process runs the API and, when configured, the Telegram bot
(ADR-0002). The bot's lifecycle is tied to the API's lifespan."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telegram import Bot

from training_coach import __version__
from training_coach.api.plan import router as plan_router
from training_coach.api.security import security_headers_middleware
from training_coach.bot.app import build_bot, send_with_retry
from training_coach.config import Settings, get_settings
from training_coach.db.session import make_engine, make_session_factory
from training_coach.logging import configure_logging
from training_coach.services import backup

log = structlog.get_logger(__name__)


class Health(BaseModel):
    status: str
    version: str
    bot_enabled: bool


def _owner_notifier(settings: Settings, telegram: Bot | None) -> backup.Notify | None:
    """A failed backup is worth a message, to the owner only (ADR-0009)."""
    owner = settings.telegram_allowed_user_id
    if telegram is None or owner is None:
        return None

    async def notify(text: str) -> bool:
        return await send_with_retry(telegram, owner, text)

    return notify


def _start_backups(settings: Settings, notify: backup.Notify | None) -> asyncio.Task[None] | None:
    """Nightly backups (ADR-0010) run whenever the database is a file, bot or no bot."""
    source = backup.database_path(settings.database_url)
    if source is None:
        return None
    task = asyncio.create_task(
        backup.run_nightly(source, source.parent / "backups", settings.tz, notify),
        name="backup.nightly",
    )
    task.add_done_callback(_report_death)
    return task


def _report_death(task: "asyncio.Task[None]") -> None:
    """The loop never returns or raises on its own; if it does, say so rather than stop
    backing up in silence."""
    if task.cancelled():
        return
    error = task.exception()
    log.error("backup.loop_died", error=type(error).__name__ if error else "returned")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings.database_url) if settings.bot_enabled else None
        bot = build_bot(settings, make_session_factory(engine)) if engine is not None else None
        if bot is not None:
            await bot.initialize()
            await bot.start()
            assert bot.updater is not None  # noqa: S101 - always set by the default builder
            await bot.updater.start_polling(drop_pending_updates=False)
            log.info("bot.started")
        else:
            log.warning("bot.disabled", reason="telegram token or allowed user id not set")
        nightly = _start_backups(settings, _owner_notifier(settings, bot.bot if bot else None))
        try:
            yield
        finally:
            if nightly is not None:
                nightly.cancel()
                # A loop that died was logged by its done-callback; never let it stop shutdown.
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await nightly
            if bot is not None:
                assert bot.updater is not None  # noqa: S101
                await bot.updater.stop()
                await bot.stop()
                await bot.shutdown()
                log.info("bot.stopped")
            if engine is not None:
                engine.dispose()

    app = FastAPI(
        title="Training Coach",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
    )
    app.middleware("http")(security_headers_middleware)

    @app.get("/healthz", response_model=Health, tags=["ops"])
    async def healthz() -> Health:
        return Health(status="ok", version=__version__, bot_enabled=settings.bot_enabled)

    app.include_router(plan_router)

    # Mounted last so API routes always win over static files.
    if settings.web_dist_dir is not None and settings.web_dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.web_dist_dir, html=True), name="web")

    return app
