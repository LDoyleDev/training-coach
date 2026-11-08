"""FastAPI application. One process runs the API and, when configured, the Telegram bot
(ADR-0002). The bot's lifecycle is tied to the API's lifespan."""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker
from telegram import Bot

from training_coach import __version__
from training_coach.api.account import router as account_router
from training_coach.api.ai import router as ai_router
from training_coach.api.alerts import Forget, Send
from training_coach.api.auth import router as auth_router
from training_coach.api.band import router as band_router
from training_coach.api.body import router as body_router
from training_coach.api.body_settings import router as body_settings_router
from training_coach.api.cardio import router as cardio_router
from training_coach.api.change import router as change_router
from training_coach.api.connections import router as connections_router
from training_coach.api.consents import router as consents_router
from training_coach.api.coverage import router as coverage_router
from training_coach.api.daily_check import router as daily_check_router
from training_coach.api.day import router as day_router
from training_coach.api.equipment import router as equipment_router
from training_coach.api.fitness import router as fitness_router
from training_coach.api.habits import router as habits_router
from training_coach.api.health import router as health_router
from training_coach.api.heart_rate import router as heart_rate_router
from training_coach.api.home import router as home_router
from training_coach.api.ingest import account_router as ingest_account_router
from training_coach.api.ingest import router as ingest_router
from training_coach.api.invites import router as invites_router
from training_coach.api.log import router as log_router
from training_coach.api.mcp import PER_CONNECTION
from training_coach.api.mcp import router as mcp_router
from training_coach.api.notices import router as notices_router
from training_coach.api.oauth import PER_ADDRESS
from training_coach.api.oauth import router as oauth_router
from training_coach.api.passkeys import router as passkeys_router
from training_coach.api.photos import router as photos_router
from training_coach.api.plan import router as plan_router
from training_coach.api.progress import router as progress_router
from training_coach.api.proposals import router as proposals_router
from training_coach.api.readiness import router as readiness_router
from training_coach.api.region import region_guard
from training_coach.api.residence import router as residence_router
from training_coach.api.review import router as review_router
from training_coach.api.security import request_guard, security_headers_middleware
from training_coach.api.session import router as session_router
from training_coach.api.settings import Reschedule
from training_coach.api.settings import router as settings_router
from training_coach.api.telegram_link import router as telegram_link_router
from training_coach.bot.app import (
    ALLOWED_UPDATES,
    ANNOUNCE,
    FORGET,
    RESCHEDULE,
    build_bot,
    send_with_retry,
)
from training_coach.config import Settings, get_settings
from training_coach.db.session import make_engine, make_session_factory, session_scope
from training_coach.domain.rate_limit import RateLimit
from training_coach.logging import configure_logging
from training_coach.services import backup, left_list, telegram_link, users, wind_down
from training_coach.services.user_settings import Prefs

log = structlog.get_logger(__name__)


class Health(BaseModel):
    status: str
    # Only for callers on the Pi (the deploy waits for its version, the heartbeat): a request
    # through the tunnel gets the status alone (security review, 2026-10-24).
    version: str | None = None
    bot_enabled: bool | None = None


def _sender(telegram: Bot | None) -> Send | None:
    """Messages to a person's own chat: the alerts about their sign-ins (ADR-0040)."""
    if telegram is None:
        return None

    async def send(chat: int, text: str) -> bool:
        return await send_with_retry(telegram, chat, text)

    return send


def _owner_notifier(telegram: Bot | None, owner: int | None) -> backup.Notify | None:
    """A failed backup is worth a message, to the owner's linked chat only (ADR-0009)."""
    if telegram is None or owner is None:
        return None

    async def notify(text: str) -> bool:
        return await send_with_retry(telegram, owner, text)

    return notify


def _on_loop(reschedule: Callable[[Prefs], None], jobs_for: int) -> Reschedule:
    """The settings page moves the bot's jobs on the bot's own event loop: sync routes run in
    worker threads, and the job queue isn't thread-safe. The bot's jobs are ``jobs_for``'s
    (the owner's) until each person has their own, so anyone else's change moves nothing."""
    loop = asyncio.get_running_loop()

    def call(user: int, prefs: Prefs) -> None:
        if user != jobs_for:
            return
        loop.call_soon_threadsafe(reschedule, prefs)

    return call


def _bot_loop(forget: Forget) -> Forget:
    """Forgetting a person runs on the bot's own event loop: sync routes run in worker
    threads, and the handlers' state isn't locked. It is queued after the route's commit, so
    an update the bot is already handling for them can still finish, and re-add a draft, in
    between; with their link or account gone, the gate lets nothing of theirs through again."""
    loop = asyncio.get_running_loop()

    def call(user: int) -> None:
        loop.call_soon_threadsafe(forget, user)

    return call


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


def _start_wind_down(
    settings: Settings,
    shared: sessionmaker[Session],
    send: Send | None,
    notify: backup.Notify | None,
    forget: Forget | None,
) -> asyncio.Task[None]:
    """The members' wind-down (ADR-0059), every day whatever the switch says, bot or no bot."""
    left = left_list.for_url(settings.database_url)

    def today() -> wind_down.Report:
        with session_scope(shared) as session:  # expired connect links too (ADR-0089)
            telegram_link.clear_expired(session, datetime.now(UTC))
        with session_scope(shared) as session:
            local = datetime.now(UTC).astimezone(settings.tz).date()
            return wind_down.run(session, settings.multi_user, local, left)

    async def once() -> None:
        report = await asyncio.to_thread(today)
        if forget is not None:
            for user in report.gone:
                forget(user)  # nothing of theirs waits in the bot (ADR-0089)
        await _tell_wind_down(report, send, notify)

    task = asyncio.create_task(wind_down.run_daily(once, settings.tz), name="wind_down.daily")
    task.add_done_callback(_report_wind_down_death)
    return task


async def _tell_wind_down(
    report: wind_down.Report, send: Send | None, notify: backup.Notify | None
) -> None:
    """Each member in their own chat; the owner gets the count and the day, never who. A
    message that can't go out is logged, never stops the rest."""
    messages = [(t.chat, wind_down.closing_text(t.on)) for t in report.closing]
    messages += [(t.chat, wind_down.ERASED) for t in report.erased]
    for chat, text in messages:
        if send is not None and chat is not None:
            try:
                await send(chat, text)
            except Exception as exc:  # the next member is still told
                log.warning("wind_down.tell_failed", error=type(exc).__name__)
    if report.closing and notify is not None:
        count = len(report.closing)
        who = "1 member" if count == 1 else f"{count} members"
        on = wind_down.day(report.closing[0].on)
        with contextlib.suppress(Exception):
            await notify(
                f"TC_MULTI_USER is off: Training Coach is closing to {who} (told on Telegram if "
                f"linked). Their data is erased on {on} unless you switch it back on before then."
            )


def _report_wind_down_death(task: "asyncio.Task[None]") -> None:
    if task.cancelled():
        return
    error = task.exception()
    log.error("wind_down.loop_died", error=type(error).__name__ if error else "returned")


LEFT_BACK = (
    "{count} who left Training Coach are back in the database, from a restored backup. Nothing "
    "was deleted: run `training-coach forget-left --apply` (backup-restore runbook, ADR-0088)."
)


async def _left_back(
    settings: Settings, shared: sessionmaker[Session], notify: backup.Notify | None
) -> None:
    """After a restore, anyone on the left list who is back is named, never deleted here: the
    owner deletes them again on purpose (ADR-0088). Only a warning, so it never stops the app
    starting: a list it can't read (malformed, or put back with the wrong owner) is logged and
    told instead, as the owner needs the app up most just after a restore."""
    try:
        path = left_list.for_url(settings.database_url)
        if path is None:
            return
        entries = left_list.read(path)
        with session_scope(shared) as session:
            back = left_list.back(session, entries)
        if not back:
            return
        log.error("left.back", users=back)
        text = LEFT_BACK.format(count=f"{len(back)} people" if len(back) > 1 else "1 person")
    except Exception as exc:  # a warning step must not stop start-up
        log.error("left.check_failed", error=type(exc).__name__)
        text = LEFT_UNREADABLE
    if notify is not None:
        with contextlib.suppress(Exception):
            await notify(text)


LEFT_UNREADABLE = (
    "Training Coach couldn't read its list of people who left (left-users.json), so it can't "
    "tell whether a restore brought anyone back. Check the file (backup-restore runbook, "
    "ADR-0088)."
)


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
    "/plan/edit",
    "/readiness",
    "/review",
    "/connect",  # the consent page for connecting an AI app (ADR-0047 C)
    "/join",  # an invite (ADR-0059); its routes answer 404 while TC_MULTI_USER is off
)


# What makes the web app installable (D3), with the type a browser expects. The service worker
# is checked on every visit (no-cache) so a deploy reaches the phone on the next page opened.
INSTALL_FILES = {
    "/sw.js": "text/javascript",
    "/manifest.webmanifest": "application/manifest+json",
}


def _add_install_files(app: FastAPI, dist: Path) -> None:
    for path, media_type in INSTALL_FILES.items():
        file = dist / path.removeprefix("/")
        if not file.is_file():  # an older build, or a test with only index.html
            continue

        async def serve(file: Path = file, media_type: str = media_type) -> FileResponse:
            return FileResponse(file, media_type=media_type, headers={"Cache-Control": "no-cache"})

        app.add_api_route(path, serve, include_in_schema=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    # One engine for the web routes and the bot. Sign-in reads through unbound sessions
    # (services.auth); everything personal goes through sessions bound to the signed-in user.
    engine = make_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        bot = None
        sends_only: Bot | None = None  # the bot off, its alerts still sent (a clash, below)
        owner = users.OWNER  # whose jobs the bot runs (set again by link_owner)
        owner_chat: int | None = None  # where the owner's own alerts go: their linked chat
        if settings.bot_enabled:
            # bot_enabled means the token and the allowed account are both set.
            allowed = settings.telegram_allowed_user_id
            assert allowed is not None  # noqa: S101 - guaranteed by bot_enabled
            # The owner's data only (ADR-0026): link the allowed account to its user, then hand
            # the bot sessions bound to that user.
            with session_scope(make_session_factory(engine)) as session:
                owner = users.link_owner(session, allowed)
                owner_chat = users.telegram_chat(session, owner)
            if owner_chat == allowed:
                bot = build_bot(settings, make_session_factory(engine, user_id=owner))
            else:
                # Someone else holds the configured account (logged by link_owner). Until the
                # bot finds each person from the sender (ADR-0089), it answers that account as
                # the owner, so it stays off rather than hand a member the owner's data.
                log.error("bot.disabled", reason="the configured account is someone else's")
                # Alerts still go out (each to its own person's linked chat), from a Bot that
                # only sends: no polling, no handlers, nothing to answer.
                assert settings.telegram_bot_token is not None  # noqa: S101 - bot_enabled
                sends_only = Bot(settings.telegram_bot_token.get_secret_value())
        if bot is not None:
            await bot.initialize()
            await bot.start()
            assert bot.updater is not None  # noqa: S101 - always set by the default builder
            # Only messages and button presses: nothing else gets past the gate (ADR-0089).
            await bot.updater.start_polling(
                drop_pending_updates=False, allowed_updates=list(ALLOWED_UPDATES)
            )
            log.info("bot.started")
        elif not settings.bot_enabled:
            log.warning("bot.disabled", reason="telegram token or allowed user id not set")
        app.state.reschedule = (
            _on_loop(bot.bot_data[RESCHEDULE], owner) if bot is not None else None
        )
        telegram = bot.bot if bot is not None else sends_only
        app.state.send = _sender(telegram)  # sign-in alerts (ADR-0040)
        # For a member's connect link, t.me/<bot> (ADR-0089): known once the bot has started.
        app.state.bot_username = bot.bot.username if bot is not None else None
        # Proposals from a connected AI go to Telegram as they come (ADR-0058).
        app.state.announce_proposals = bot.bot_data[ANNOUNCE] if bot is not None else None
        app.state.forget = _bot_loop(bot.bot_data[FORGET]) if bot is not None else None
        notify = _owner_notifier(telegram, owner_chat)
        app.state.notify = notify  # ops: a failed backup
        nightly = _start_backups(settings, notify)
        closing = _start_wind_down(
            settings, make_session_factory(engine), app.state.send, notify, app.state.forget
        )
        await _left_back(settings, make_session_factory(engine), notify)
        try:
            yield
        finally:
            closing.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await closing
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
            if sends_only is not None:
                with contextlib.suppress(Exception):  # it made no requests of its own to close
                    await sends_only.shutdown()
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
    app.middleware("http")(region_guard)  # the EU and EEA only (ADR-0085), before any route
    app.middleware("http")(security_headers_middleware)  # outermost: headers on refusals too
    app.state.shared_sessions = make_session_factory(engine)
    app.state.engine = engine
    app.state.settings = settings
    # Unauthenticated OAuth and MCP calls, per client address and route, a minute.
    app.state.address_limits = RateLimit(PER_ADDRESS, 60)
    app.state.connection_limits = RateLimit(PER_CONNECTION, 60)  # /mcp, per connection

    @app.get("/healthz", response_model=Health, response_model_exclude_none=True, tags=["ops"])
    async def healthz(request: Request) -> Health:
        # Cloudflare adds CF-Connecting-IP to every request it passes on and a visitor can't
        # remove it; callers on the Pi reach the port without it.
        if "cf-connecting-ip" in request.headers:
            return Health(status="ok")
        return Health(status="ok", version=__version__, bot_enabled=settings.bot_enabled)

    app.include_router(plan_router)
    app.include_router(notices_router)
    app.include_router(invites_router)
    app.include_router(coverage_router)
    app.include_router(equipment_router)
    app.include_router(auth_router)
    app.include_router(passkeys_router)
    app.include_router(account_router)
    app.include_router(telegram_link_router)
    app.include_router(residence_router)
    app.include_router(ai_router)
    app.include_router(session_router)
    app.include_router(cardio_router)
    app.include_router(log_router)
    app.include_router(band_router)
    app.include_router(change_router)
    app.include_router(fitness_router)
    app.include_router(body_router)
    app.include_router(body_settings_router)
    app.include_router(photos_router)
    app.include_router(home_router)
    app.include_router(progress_router)
    app.include_router(readiness_router)
    app.include_router(consents_router)
    app.include_router(daily_check_router)
    app.include_router(ingest_router)
    app.include_router(ingest_account_router)
    app.include_router(heart_rate_router)
    app.include_router(health_router)
    app.include_router(habits_router)
    app.include_router(settings_router)
    app.include_router(review_router)
    app.include_router(oauth_router)
    app.include_router(mcp_router)
    app.include_router(connections_router)
    app.include_router(proposals_router)
    app.include_router(day_router)

    # Mounted last so API routes always win over static files.
    dist = settings.web_dist_dir
    if dist is not None and dist.is_dir():
        index = dist / "index.html"

        async def page() -> FileResponse:
            return FileResponse(index)

        for path in SPA_PAGES:  # the app's own router shows the page
            app.add_api_route(path, page, include_in_schema=False)
        _add_install_files(app, dist)
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")

    return app
