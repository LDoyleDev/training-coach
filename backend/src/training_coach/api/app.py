"""FastAPI application. One process runs the API and, when configured, the Telegram bot
(ADR-0002). The bot's lifecycle is tied to the API's lifespan."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from telegram import Bot

from training_coach import __version__
from training_coach.api.account import router as account_router
from training_coach.api.auth import router as auth_router
from training_coach.api.body import router as body_router
from training_coach.api.fitness import router as fitness_router
from training_coach.api.passkeys import router as passkeys_router
from training_coach.api.photos import router as photos_router
from training_coach.api.plan import router as plan_router
from training_coach.api.progress import router as progress_router
from training_coach.api.readiness import router as readiness_router
from training_coach.api.security import request_guard, security_headers_middleware
from training_coach.api.session import router as session_router
from training_coach.bot.app import build_bot, send_with_retry
from training_coach.config import Settings, get_settings
from training_coach.db.session import make_engine, make_session_factory, session_scope
from training_coach.logging import configure_logging
from training_coach.services import backup, users

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


# Pages of the web app that are reached by URL, not only from within it (a link from the bot).
SPA_PAGES = (
    "/signin",
    "/account",
    "/session",
    "/tests",
    "/body",
    "/progress",
    "/plan",
    "/readiness",
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    # One engine for the web routes and the bot. Sign-in reads through unbound sessions
    # (services.auth); everything personal goes through sessions bound to the signed-in user.
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        bot = None
        if settings.bot_enabled:
            # bot_enabled means the token and the allowed account are both set.
            allowed = settings.telegram_allowed_user_id
            assert allowed is not None  # noqa: S101 - guaranteed by bot_enabled
            # The owner's data only (ADR-0026): link the allowed account to its user, then hand
            # the bot sessions bound to that user.
            with session_scope(make_session_factory(engine)) as session:
                owner = users.link_owner(session, allowed)
            bot = build_bot(settings, make_session_factory(engine, user_id=owner))
        if bot is not None:
            await bot.initialize()
            await bot.start()
            assert bot.updater is not None  # noqa: S101 - always set by the default builder
            await bot.updater.start_polling(drop_pending_updates=False)
            log.info("bot.started")
        else:
            log.warning("bot.disabled", reason="telegram token or allowed user id not set")
        notify = _owner_notifier(settings, bot.bot if bot else None)
        app.state.notify = notify  # sign-in alerts (ADR-0040)
        nightly = _start_backups(settings, notify)
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
            engine.dispose()

    app = FastAPI(
        title="Training Coach",
        version=__version__,
        lifespan=lifespan,
        docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.environment != "production" else None,
    )
    app.middleware("http")(request_guard(settings.public_url))
    app.middleware("http")(security_headers_middleware)  # outermost: headers on refusals too
    app.state.shared_sessions = make_session_factory(engine)
    app.state.engine = engine
    app.state.settings = settings

    @app.get("/healthz", response_model=Health, tags=["ops"])
    async def healthz() -> Health:
        return Health(status="ok", version=__version__, bot_enabled=settings.bot_enabled)

    app.include_router(plan_router)
    app.include_router(auth_router)
    app.include_router(passkeys_router)
    app.include_router(account_router)
    app.include_router(session_router)
    app.include_router(fitness_router)
    app.include_router(body_router)
    app.include_router(photos_router)
    app.include_router(progress_router)
    app.include_router(readiness_router)

    # Mounted last so API routes always win over static files.
    dist = settings.web_dist_dir
    if dist is not None and dist.is_dir():
        index = dist / "index.html"

        async def page() -> FileResponse:
            return FileResponse(index)

        for path in SPA_PAGES:  # the app's own router shows the page
            app.add_api_route(path, page, include_in_schema=False)
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")

    return app
