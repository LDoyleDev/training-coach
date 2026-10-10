"""Telegram bot. Long polling only: no inbound port is ever opened (ADR-0009).

Every command handler is registered behind ``owner_only`` so the bot ignores anyone who
is not ``TC_TELEGRAM_ALLOWED_USER_ID``. Button presses (callback queries) can't take a filter,
so ``Handlers.button`` checks the sender itself before doing anything.
"""

import asyncio
import warnings
from collections.abc import Callable, Coroutine, Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
    Update,
)
from telegram.error import NetworkError, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.warnings import PTBDeprecationWarning

from training_coach.bot import buttons, logging_flow
from training_coach.bot import habits as habits_ui
from training_coach.bot import progress as progress_ui
from training_coach.bot import settings as settings_ui
from training_coach.bot import stretching as stretching_ui
from training_coach.bot.buttons import edit_quietly
from training_coach.bot.logging_flow import LogHandlers
from training_coach.bot.messages import (
    NO_PLAN,
    NUDGE,
    NUDGE_TEST,
    SOMETHING_WENT_WRONG,
    STALE,
    picked_text,
    pushed_text,
    rest_text,
    review_text,
    session_detail_text,
    test_day_text,
    tests_where,
    today_text,
    week_text,
)
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.queue import local_date
from training_coach.services import (
    auth,
    blocks,
    habits,
    passkeys,
    queue_actions,
    review,
    user_settings,
)
from training_coach.services.groq import GroqClient
from training_coach.services.today import session_plan
from training_coach.services.today import today as todays_session
from training_coach.services.today import week as upcoming_week
from training_coach.services.user_settings import Prefs

log = structlog.get_logger(__name__)

HELP_TEXT = (
    "Training Coach\n\n"
    "/today - today's session with targets\n"
    "/week - the next 7 sessions\n"
    "/progress - each exercise's step, last session and best\n"
    "/review - this week so far: sessions, sets per muscle, bests\n"
    "/habits - tick today's habits: morning light, protein, wind-down\n"
    "/settings - message times, nudges, habits, pause\n"
    "/login - sign in to the web app\n"
    "/recover - sign in without your passkey (lost phone); signs out other devices\n"
    "/help - this message\n\n"
    "Log a workout by sending it as a message, like: pull-ups 8 8 7, dips 12 11 10. "
    "A voice note works too. I'll show what I understood before saving anything.\n\n"
    "To log a past day, put its date on the first line, like: yesterday, Tue or 29 Sep. "
    "Add the session (Legs) or rest after the date if you like.\n\n"
    "The session for the day also arrives every morning, with buttons to start it, "
    "take a rest day or swap it."
)
LOGIN_TEXT = "Sign in to Training Coach. The link works once, for 10 minutes:"
LOGIN_PASSKEY = (
    "Sign in with your fingerprint (your passkey) here:\n{url}/signin\n\n"
    "Lost your phone or passkey? Send /recover."
)
RECOVER_TEXT = (
    "Recovery link for Training Coach. It works once, for 10 minutes. It signs you in without "
    "your fingerprint, signs out every other device and removes your passkeys (add yours "
    "again after):"
)
LOGIN_OFF = "Web sign-in isn't set up yet: TC_PUBLIC_URL is missing on the server."
MORNING_JOB = "morning"
NUDGE_JOB = "nudge"
REVIEW_JOB = "weekly-review"
SUNDAY = 0  # PTB counts days from Sunday (0) to Saturday (6)
Job = Callable[[ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]


def owner_only(settings: Settings) -> filters.BaseFilter:
    if settings.telegram_allowed_user_id is None:
        raise ValueError("TC_TELEGRAM_ALLOWED_USER_ID must be set to run the bot")
    # Only in the private chat with the owner: in a group, links and logs would be seen by
    # everyone in it (security review, ADR-0040).
    return filters.ChatType.PRIVATE & filters.User(user_id=settings.telegram_allowed_user_id)


def _retry_seconds(exc: RetryAfter) -> float:
    """``retry_after`` is an int today and a timedelta in a future PTB; accept both."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PTBDeprecationWarning)
        value = exc.retry_after
    return value.total_seconds() if isinstance(value, timedelta) else float(value)


async def send_with_retry(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    attempts: int = 3,
    backoff: float = 2.0,
) -> bool:
    """Send a scheduled message. Network errors are retried with backoff and flood control
    is waited out; any other Telegram error (blocked, bad chat) gives up. False if not sent."""
    for attempt in range(1, attempts + 1):
        try:
            await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)
        except RetryAfter as exc:
            log.warning("bot.send_failed", attempt=attempt, error="RetryAfter")
            if attempt < attempts:
                await asyncio.sleep(_retry_seconds(exc))
        except NetworkError as exc:
            log.warning("bot.send_failed", attempt=attempt, error=type(exc).__name__)
            if attempt < attempts:
                await asyncio.sleep(backoff * 2 ** (attempt - 1))
        except TelegramError as exc:
            log.warning("bot.send_failed", attempt=attempt, error=type(exc).__name__)
            return False
        else:
            return True
    return False


class Handlers:
    """Thin adapters: read through ``services``, format with ``messages``, reply."""

    def __init__(self, settings: Settings, sessions: sessionmaker[Session]) -> None:
        self.settings = settings
        self.sessions = sessions

    def _local_today(self) -> date:
        return local_date(datetime.now(UTC), self.settings.tz)

    def _today(self) -> tuple[str, InlineKeyboardMarkup | None]:
        """Today's message, with the Start / Rest today / Swap buttons when there is a plan."""
        with session_scope(self.sessions) as session:
            plan = todays_session(session, self._local_today(), self.settings.tz)
            if plan is None:
                return NO_PLAN, None
            if plan.test_day is not None:
                where = tests_where(self.settings.public_url)
                instead = buttons.instead(plan.session.template_id, plan.session.name)
                return test_day_text(plan, where), instead
            return today_text(plan), buttons.morning(plan.session.template_id)

    async def help(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message is not None:
            await update.effective_message.reply_text(HELP_TEXT)

    async def today(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_message is not None:
            text, markup = self._today()
            await update.effective_message.reply_text(text, reply_markup=markup)

    async def login(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """A one-time sign-in link for the web app (ADR-0036): works once, for 10 minutes."""
        message = update.effective_message
        if message is None:
            return
        if self.settings.public_url is None:
            await message.reply_text(LOGIN_OFF)
            return
        with session_scope(self.sessions) as session:
            # Once a passkey exists the fingerprint signs in, not a link (ADR-0040).
            keyed = bool(passkeys.keys(session))
            token = None if keyed else auth.create_link(session, datetime.now(UTC))
        if token is None:
            await message.reply_text(
                LOGIN_PASSKEY.format(url=self.settings.public_url),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            log.info("bot.login_passkey_pointer_sent")
            return
        await message.reply_text(
            f"{LOGIN_TEXT}\n{self.settings.public_url}/signin#{token}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        log.info("bot.login_link_sent")

    async def recover(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """A recovery link (ADR-0040): signs in without a passkey and signs out every other
        browser; the web app then sends an alert here."""
        message = update.effective_message
        if message is None:
            return
        if self.settings.public_url is None:
            await message.reply_text(LOGIN_OFF)
            return
        with session_scope(self.sessions) as session:
            token = auth.create_link(session, datetime.now(UTC), purpose=auth.RECOVER)
        await message.reply_text(
            f"{RECOVER_TEXT}\n{self.settings.public_url}/signin#{token}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        log.info("bot.recover_link_sent")

    async def week(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        with session_scope(self.sessions) as session:
            days = upcoming_week(session, self._local_today(), tz=self.settings.tz)
            text = NO_PLAN if days is None else week_text(days)
        if update.effective_message is not None:
            await update.effective_message.reply_text(text)

    async def morning(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            with session_scope(self.sessions) as session:
                paused = user_settings.load(session).paused
            text, markup = self._today()
        except SQLAlchemyError as exc:
            log.error("bot.morning_failed", error=type(exc).__name__)
            return
        if paused:
            log.info("bot.morning_skipped", reason="paused")
            return
        assert self.settings.telegram_allowed_user_id is not None  # noqa: S101 - owner_only
        if await send_with_retry(
            context.bot, self.settings.telegram_allowed_user_id, text, reply_markup=markup
        ):
            log.info("bot.morning_sent")
        else:
            log.error("bot.morning_failed")

    async def weekly_review(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sunday's review of the week (#73), unless paused."""
        try:
            with session_scope(self.sessions) as session:
                if user_settings.load(session).paused:
                    log.info("bot.review_skipped", reason="paused")
                    return
                text = review_text(review.weekly(session, self._local_today(), self.settings.tz))
        except SQLAlchemyError as exc:
            log.error("bot.review_failed", error=type(exc).__name__)
            return
        assert self.settings.telegram_allowed_user_id is not None  # noqa: S101 - owner_only
        if await send_with_retry(context.bot, self.settings.telegram_allowed_user_id, text):
            log.info("bot.review_sent")
        else:
            log.error("bot.review_failed")

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """A morning-message button. Strangers get nothing, not even an answer (T1)."""
        query = update.callback_query
        if (
            query is None
            or update.effective_user is None
            or update.effective_user.id != self.settings.telegram_allowed_user_id
        ):
            return
        press = buttons.parse(query.data)
        if press is None or not isinstance(query.message, Message):
            await query.answer()
            return
        reply = query.message.reply_text
        current = query.message.reply_markup

        def keep(markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup | None:
            """Change only the morning rows; habit buttons on the same message stay (#91)."""
            rows = markup.inline_keyboard if markup is not None else ()
            return buttons.merged(current, buttons.PREFIX, rows)

        on = self._local_today()
        tid = press.template_id

        if press.action == "swap":
            await query.answer()
            await edit_quietly(query.edit_message_reply_markup(keep(buttons.swap(tid))))
            return
        if press.action == "back":
            await query.answer()
            await edit_quietly(query.edit_message_reply_markup(keep(buttons.morning(tid))))
            return
        if press.action == "pickmenu":
            with session_scope(self.sessions) as session:
                markup = buttons.pick(tid, queue_actions.choices(session))
            await query.answer()
            await edit_quietly(query.edit_message_reply_markup(keep(markup)))
            return
        if press.action == "start":
            with session_scope(self.sessions) as session:
                plan = session_plan(session, tid, blocks.current(session, on, self.settings.tz))
            await query.answer()
            await reply(STALE if plan is None else session_detail_text(plan))
            return

        # Actions that change the queue: one transaction, then retire the old buttons.
        with session_scope(self.sessions) as session:
            text: str | None
            new_markup: InlineKeyboardMarkup | None = None
            if press.action == "rest":
                outcome = queue_actions.rest_today(session, tid, on)
                text = rest_text(outcome) if outcome else None
            elif press.action == "push":
                name = queue_actions.push_to_tomorrow(session, tid, on)
                text = pushed_text(name) if name else None
            elif press.action == "next":
                swapped = queue_actions.swap_next(
                    session, tid, blocks.current(session, on, self.settings.tz)
                )
                text = session_detail_text(swapped) if swapped else None
                new_markup = buttons.morning(swapped.template_id) if swapped else None
            else:  # pick
                block = blocks.current(session, on, self.settings.tz)
                offered = session_plan(session, tid, block)
                picked = queue_actions.pick(session, tid, press.picked_id or 0, block)
                text = picked_text(picked, offered.name) if picked and offered else None
        await query.answer()
        await edit_quietly(query.edit_message_reply_markup(keep(None)))
        await reply(STALE if text is None else text, reply_markup=new_markup)
        log.info("bot.button", action=press.action, stale=text is None)

    async def nudge(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """The evening message, unless paused: the nudge when it's on and nothing is logged
        today, and the habit buttons when they're on (D5). Both go in one message."""
        today = self._local_today()
        try:
            with session_scope(self.sessions) as session:
                prefs = user_settings.load(session)
                logged = user_settings.anything_logged(session, today)
                plan = todays_session(session, today, self.settings.tz)
                ticked = habits.checked(session, today)
        except SQLAlchemyError as exc:
            log.error("bot.nudge_failed", error=type(exc).__name__)
            return
        nudge = not prefs.paused and prefs.nudges_enabled and not logged and plan is not None
        habit_rows = (
            habits_ui.rows(today, ticked, prefs.protein_g)
            if prefs.habits_enabled and not prefs.paused
            else []
        )
        if not nudge and not habit_rows:
            log.info(
                "bot.nudge_skipped",
                paused=prefs.paused,
                enabled=prefs.nudges_enabled,
                logged=logged,
                plan=plan is not None,
            )
            return
        parts: list[str] = []
        rows: list[Sequence[InlineKeyboardButton]] = []
        if nudge and plan is not None and plan.test_day is not None:
            where = tests_where(self.settings.public_url)
            parts.append(NUDGE_TEST.format(name=plan.test_day.name, where=where))
            rows += buttons.instead(plan.session.template_id, plan.session.name).inline_keyboard
        elif nudge and plan is not None:
            parts.append(NUDGE.format(session=plan.session.name))
            rows += buttons.morning(plan.session.template_id).inline_keyboard
        if habit_rows:
            parts.append(habits_ui.evening(prefs.protein_g))
            rows += habit_rows
        assert self.settings.telegram_allowed_user_id is not None  # noqa: S101 - owner_only
        if await send_with_retry(
            context.bot,
            self.settings.telegram_allowed_user_id,
            "\n\n".join(parts),
            reply_markup=InlineKeyboardMarkup(rows),
        ):
            log.info("bot.nudge_sent", nudge=nudge, habits=bool(habit_rows))
        else:
            log.error("bot.nudge_failed")

    async def error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log any handler failure (type only, never the message) and tell the owner."""
        log.error("bot.handler_failed", error=type(context.error).__name__)
        if (
            isinstance(update, Update)
            and update.effective_user is not None
            and update.effective_user.id == self.settings.telegram_allowed_user_id
            and update.effective_message is not None
        ):
            await update.effective_message.reply_text(SOMETHING_WENT_WRONG)


def _schedule_daily(
    application: Application,  # type: ignore[type-arg]  # see build_bot
    name: str,
    callback: Job,
    at: time,
    tz: ZoneInfo,
    days: tuple[int, ...] = tuple(range(7)),
) -> None:
    """(Re)schedule a job at local wall-clock time ``at`` on ``days`` (PTB: 0 is Sunday).

    The time carries the user's timezone, so the job follows DST: 07:30 stays 07:30 local.
    """
    job_queue = application.job_queue
    assert job_queue is not None  # noqa: S101 - the job-queue extra is a dependency
    for job in job_queue.get_jobs_by_name(name):
        job.schedule_removal()
    job_queue.run_daily(callback, time=at.replace(tzinfo=tz), days=days, name=name)
    log.info("bot.job_scheduled", job=name, at=at.isoformat())


def schedule_morning(application: Application, handlers: Handlers, at: time) -> None:  # type: ignore[type-arg]  # see build_bot
    _schedule_daily(application, MORNING_JOB, handlers.morning, at, handlers.settings.tz)


def schedule_jobs(application: Application, handlers: Handlers, prefs: Prefs) -> None:  # type: ignore[type-arg]  # see build_bot
    """Schedule the morning message, the evening nudge and Sunday's review from the settings."""
    tz = handlers.settings.tz
    schedule_morning(application, handlers, prefs.morning_time)
    _schedule_daily(application, NUDGE_JOB, handlers.nudge, prefs.nudge_time, tz)
    _schedule_daily(
        application, REVIEW_JOB, handlers.weekly_review, prefs.review_time, tz, days=(SUNDAY,)
    )


# PTB's Application takes six type parameters, all fixed by the default builder; spelling them
# out adds nothing, so the bare generic is deliberate.
def build_bot(
    settings: Settings, sessions: sessionmaker[Session], groq: GroqClient | None = None
) -> Application:  # type: ignore[type-arg]  # see the comment above
    if settings.telegram_bot_token is None:
        raise ValueError("TC_TELEGRAM_BOT_TOKEN must be set to run the bot")
    application = (
        Application.builder().token(settings.telegram_bot_token.get_secret_value()).build()
    )
    allowed = owner_only(settings)
    handlers = Handlers(settings, sessions)
    application.add_handler(CommandHandler(["start", "help"], handlers.help, filters=allowed))
    application.add_handler(CommandHandler("today", handlers.today, filters=allowed))
    application.add_handler(CommandHandler("week", handlers.week, filters=allowed))
    application.add_handler(CommandHandler("login", handlers.login, filters=allowed))
    application.add_handler(CommandHandler("recover", handlers.recover, filters=allowed))
    progress_handlers = progress_ui.ProgressHandlers(settings, sessions)
    application.add_handler(CommandHandler("progress", progress_handlers.command, filters=allowed))
    application.add_handler(CommandHandler("review", progress_handlers.review, filters=allowed))
    stretch_handlers = stretching_ui.StretchHandlers(settings, sessions)
    application.add_handler(
        CallbackQueryHandler(stretch_handlers.button, pattern=rf"^{stretching_ui.PREFIX}:")
    )
    habit_handlers = habits_ui.HabitHandlers(settings, sessions)
    application.add_handler(CommandHandler("habits", habit_handlers.command, filters=allowed))
    application.add_handler(
        CallbackQueryHandler(habit_handlers.button, pattern=rf"^{habits_ui.PREFIX}:")
    )
    application.add_handler(CallbackQueryHandler(handlers.button, pattern=rf"^{buttons.PREFIX}:"))

    settings_handlers = settings_ui.SettingsHandlers(
        settings, sessions, lambda _context, prefs: schedule_jobs(application, handlers, prefs)
    )
    application.add_handler(CommandHandler("settings", settings_handlers.command, filters=allowed))
    application.add_handler(
        CallbackQueryHandler(settings_handlers.button, pattern=rf"^{settings_ui.PREFIX}:")
    )
    groq = (
        GroqClient(
            settings.groq_api_key,
            transcribe_model=settings.groq_transcribe_model,
            parse_model=settings.groq_parse_model,
        )
        if groq is None and settings.groq_api_key is not None
        else groq
    )
    log_handlers = LogHandlers(settings, sessions, groq)
    application.add_handler(
        CallbackQueryHandler(log_handlers.button, pattern=rf"^{logging_flow.PREFIX}:")
    )
    application.add_handler(
        CallbackQueryHandler(progress_handlers.button, pattern=rf"^{progress_ui.PREFIX}:")
    )

    async def text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """The one handler for plain text: PTB runs only the first match in a group. A pending
        /settings question gets the answer; anything else is a workout log (1-E)."""
        awaiting = context.user_data.get(settings_ui.AWAITING) if context.user_data else None
        message = update.effective_message
        words = message is not None and any(c.isalpha() for c in message.text or "")
        if awaiting and words and context.user_data is not None:
            context.user_data.pop(settings_ui.AWAITING, None)  # a log, not a time: stop asking
            awaiting = None
        if awaiting:
            await settings_handlers.typed_time(update, context)
        else:
            await log_handlers.message(update, context)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & allowed, text))
    application.add_handler(MessageHandler(filters.VOICE & allowed, log_handlers.voice))

    application.add_error_handler(handlers.error)

    try:
        with session_scope(sessions) as session:
            prefs = user_settings.load(session)
    except SQLAlchemyError as exc:  # don't block startup (ADR-0015 spirit); use the defaults
        log.error("bot.settings_unreadable", error=type(exc).__name__)
        prefs = Prefs()
    schedule_jobs(application, handlers, prefs)
    log.info("bot.built", allowed_user_id=settings.telegram_allowed_user_id)
    return application
