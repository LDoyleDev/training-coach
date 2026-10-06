"""FastAPI application. One process runs the API and, when configured, the Telegram bot
(ADR-0002). The bot's lifecycle is tied to the API's lifespan."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from training_coach import __version__
from training_coach.api.plan import router as plan_router
from training_coach.api.security import security_headers_middleware
from training_coach.bot.app import build_bot
from training_coach.config import Settings, get_settings
from training_coach.db.session import make_engine, make_session_factory
from training_coach.logging import configure_logging

log = structlog.get_logger(__name__)


class Health(BaseModel):
    status: str
    version: str
    bot_enabled: bool


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
        try:
            yield
        finally:
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
