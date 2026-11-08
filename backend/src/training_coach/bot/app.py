"""Telegram bot. Long polling only: no inbound port is ever opened (ADR-0009).

Every update meets the sender gate first (``bot.gate``, ADR-0089): only messages and button
presses in a private chat, from someone linked, get any further. Every handler is registered
through ``gate.served`` and uses the sessions of the person the gate found. The scheduled
messages are each person's own too: the morning message, the evening nudge and Sunday's review
at their own times (``bot.schedules``), and the band, proposal and plan-notice checks for
everyone the gate would serve (``Gate.everyone``).
"""

import asyncio
import warnings
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

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
    TypeHandler,
    filters,
)
from telegram.warnings import PTBDeprecationWarning

from training_coach.bot import band as band_ui
from training_coach.bot import buttons, links, logging_flow
from training_coach.bot import daily_check as daily_ui
from training_coach.bot import habits as habits_ui
from training_coach.bot import notices as notices_ui
from training_coach.bot import progress as progress_ui
from training_coach.bot import proposals as proposals_ui
from training_coach.bot import schedules as schedules_ui
from training_coach.bot import settings as settings_ui
from training_coach.bot import share as share_ui
from training_coach.bot import stretching as stretching_ui
from training_coach.bot import undo as undo_ui
from training_coach.bot.buttons import edit_quietly
from training_coach.bot.gate import ALLOWED_UPDATES, ANYWHERE, AWAY_TEXT, Gate, Person
from training_coach.bot.logging_flow import LogHandlers
from training_coach.bot.messages import (
    NO_PLAN,
    NUDGE,
    NUDGE_TEST,
    SOMETHING_WENT_WRONG,
    STALE,
    picked_text,
    pushed_text,
    rest_day_text,
    rest_text,
    review_text,
    session_detail_text,
    test_day_text,
    tests_where,
    today_text,
    week_text,
)
from training_coach.config import Settings
from training_coach.db.session import session_scope, unbound_like
from training_coach.domain.consent import Category
from training_coach.domain.queue import local_date
from training_coach.services import (
    ai_comment,
    auth,
    blocks,
    daily_check,
    day_clash,
    guided,
    habits,
    health_summary,
    passkeys,
    queue_actions,
    review,
    user_settings,
)
from training_coach.services.groq import GroqClient
from training_coach.services.today import session_plan
from training_coach.services.today import today as todays_session
from training_coach.services.today import week as upcoming_week

log = structlog.get_logger(__name__)

SIGN_IN_LINES = (
    "/login - sign in to the web app\n"
    "/recover - sign in without your passkey (lost phone); signs out other devices\n"
)
HELP_TEXT = (
    "Training Coach\n\n"
    "/today - today's session with targets\n"
    "/week - the next 7 sessions\n"
    "/progress - each exercise's step, last session and best\n"
    "/review - this week so far: sessions, sets per muscle, bests\n"
    "/habits - tick today's habits: morning light, protein, wind-down\n"
    "/settings - message times, nudges, habits, pause\n"
    "/undo - take back the last rest day, swap, push or saved log\n"
    "/share - your last 4 weeks as a picture to forward (no body data or photos)\n"
    f"{SIGN_IN_LINES}"
    "/help - this message\n\n"
    "Log a workout by sending it as a message, like: pull-ups 8 8 7, dips 12 11 10. "
    "For cardio, add what it was if you like: zone 2 walk 60, or moderate cardio 45 min run. "
    "A voice note works too. I'll show what I understood before saving anything.\n\n"
    "To log a past day, put its date on the first line, like: yesterday, Tue or 29 Sep. "
    "Add the session (Legs) or rest after the date if you like.\n\n"
    "To log a different session today, name it on the first line, like: today Arms (or just "
    "Arms). It counts as done out of turn; the planned session stays next.\n\n"
    "If that day already has its session, I'll show what's there and ask whether to replace "
    "it, move it to another day or add this log to that day.\n\n"
    "The session for the day also arrives every morning, with buttons to start it, "
    "take a rest day or swap it, and three taps on how you slept, how sore you are and your "
    "energy, which say how hard to go today."
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
# A member's help leaves out /login and /recover (ADR-0089): /login only points to their
# passkey, and recovery links are the admin's to make (ADR-0059).
MEMBER_HELP_TEXT = HELP_TEXT.replace(SIGN_IN_LINES, "")
ASK_ADMIN = "Ask the admin for a recovery link."
LOGIN_MEMBER = f"Sign in with your fingerprint (your passkey) here:\n{{url}}/signin\n\n{ASK_ADMIN}"
# The gate's, named here for the API's lifespan (it starts the bot) and the tests that drive it.
__all__ = ["ALLOWED_UPDATES", "ANYWHERE", "AWAY_TEXT"]
RESCHEDULE = "reschedule"  # bot_data key: a person's new times, or new link, move their jobs
ANNOUNCE = "announce_proposals"  # bot_data key: /mcp sends a fresh proposal through this
FORGET = "forget"  # bot_data key: unlink, leave and erase drop a person's state (ADR-0089)


def _retry_seconds(exc: RetryAfter) -> float:
    """``retry_after`` is an int today and a timedelta in a future PTB; accept both."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PTBDeprecationWarning)
        value = exc.retry_after
    return value.total_seconds() if isinstance(value, timedelta) else float(value)


SENT, UNREACHABLE, REFUSED = "sent", "unreachable", "refused"


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
    sent = await send_outcome(
        bot, chat_id, text, reply_markup=reply_markup, attempts=attempts, backoff=backoff
    )
    return sent == SENT


async def send_outcome(
    bot: Bot,
    chat_id: int,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    attempts: int = 3,
    backoff: float = 2.0,
) -> str:
    """``send_with_retry``, telling apart Telegram being unreachable (``UNREACHABLE``: worth
    trying later) from it refusing this message (``REFUSED``: it would refuse it again)."""
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
            return REFUSED
        else:
            return SENT
    return UNREACHABLE


class Handlers:
    """Thin adapters: read through ``services``, format with ``messages``, reply."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.gate: Gate | None = None  # set by build_bot: who each update was let through for

    def _local_today(self) -> date:
        return local_date(datetime.now(UTC), self.settings.tz)

    def _today(self, sessions: sessionmaker[Session]) -> tuple[str, InlineKeyboardMarkup | None]:
        """Today's message, with the Start / Rest today / Swap buttons when there is a plan
        and "Open in app" under them (C1): the session, or the Tests page on a test day."""
        url = self.settings.public_url
        on = self._local_today()
        with session_scope(sessions) as session:
            plan = todays_session(session, on, self.settings.tz)
            if plan is None:
                return NO_PLAN, None
            if plan.test_day is not None:
                instead = buttons.instead(plan.session.template_id, plan.session.name)
                text = test_day_text(plan, tests_where(url))
                return text, links.with_open(instead, url, links.TESTS)
            if plan.rest_day:  # no buttons: there is nothing to start, rest or swap
                return rest_day_text(plan), links.with_open(None, url, links.SESSION)
            # The day's length chosen in the app, if any (ADR-0082).
            shown, length = guided.at_length(session, on, plan.session)
            markup = buttons.morning(plan.session.template_id)
            text = today_text(replace(plan, session=shown), length)
            return text, links.with_open(markup, url, links.SESSION)

    async def help(self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        if update.effective_message is not None:
            await update.effective_message.reply_text(HELP_TEXT if me.owner else MEMBER_HELP_TEXT)

    async def today(self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        if update.effective_message is not None:
            text, markup = self._today(me.sessions)
            await update.effective_message.reply_text(text, reply_markup=markup)

    async def login(self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        """A one-time sign-in link for the web app (ADR-0036): works once, for 10 minutes.
        A member only ever gets the pointer to their passkey: a link would sign them in."""
        message = update.effective_message
        if message is None:
            return
        if self.settings.public_url is None:
            await message.reply_text(LOGIN_OFF)
            return
        if not me.owner:
            await message.reply_text(
                LOGIN_MEMBER.format(url=self.settings.public_url),
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            log.info("bot.login_passkey_pointer_sent", member=True)
            return
        with session_scope(me.sessions) as session:
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

    async def recover(
        self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person
    ) -> None:
        """A recovery link (ADR-0040): signs in without a passkey and signs out every other
        browser; the web app then sends an alert here. The owner's only: a member asks the
        admin (ADR-0059)."""
        message = update.effective_message
        if message is None:
            return
        if not me.owner:
            await message.reply_text(ASK_ADMIN)
            log.info("bot.recover_refused", reason="member")
            return
        if self.settings.public_url is None:
            await message.reply_text(LOGIN_OFF)
            return
        with session_scope(me.sessions) as session:
            token = auth.create_link(session, datetime.now(UTC), purpose=auth.RECOVER)
        await message.reply_text(
            f"{RECOVER_TEXT}\n{self.settings.public_url}/signin#{token}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        log.info("bot.recover_link_sent")

    async def week(self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        with session_scope(me.sessions) as session:
            days = upcoming_week(session, self._local_today(), tz=self.settings.tz)
            text = NO_PLAN if days is None else week_text(days)
        if update.effective_message is not None:
            await update.effective_message.reply_text(text)

    async def morning(self, context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        """The day's session, to ``me``'s chat from ``me``'s data. The daily check comes with
        it only for someone it is open to, and the band's line only with band data (ADR-0090)."""
        on = self._local_today()
        try:
            with session_scope(me.sessions) as session:
                day_clash.sweep(session, datetime.now(UTC))  # also on days with no save
                paused = user_settings.load(session).paused
                checked = daily_check.on(session, on) is not None
                band = health_summary.morning_line(session, on)
                suggested = health_summary.suggested_sleep(session, on)
            asks = me.not_open(Category.DAILY_CHECK) is None
            if me.not_open(Category.BAND) is not None:
                band = None
            text, markup = self._today(me.sessions)
        except SQLAlchemyError as exc:
            log.error("bot.morning_failed", error=type(exc).__name__)
            return
        if paused:
            log.info("bot.morning_skipped", reason="paused")
            return
        if markup is not None and asks and not checked:  # until answered (ADR-0053)
            text = f"{text}\n\n{daily_ui.ASK}"
            if band is not None:  # what the band saw, as words only: the tap is theirs (ADR-0055)
                text = f"{text}\n{band}"
                if suggested is not None:
                    text = f"{text} {daily_ui.suggestion(suggested[0])}"
            markup = daily_ui.with_check(markup, on)
        if await send_with_retry(context.bot, me.chat, text, reply_markup=markup):
            log.info("bot.morning_sent")
        else:
            log.error("bot.morning_failed")

    async def weekly_review(self, context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        """Sunday's review of the week (#73), unless paused, and the AI comment from ``me``'s
        own key (ADR-0047 B)."""
        try:
            with session_scope(me.sessions) as session:
                if user_settings.load(session).paused:
                    log.info("bot.review_skipped", reason="paused")
                    return
                text = review_text(review.weekly(session, self._local_today(), self.settings.tz))
        except SQLAlchemyError as exc:
            log.error("bot.review_failed", error=type(exc).__name__)
            return
        if await send_with_retry(
            context.bot,
            me.chat,
            text,
            reply_markup=links.with_open(None, self.settings.public_url, links.REVIEW),
        ):
            log.info("bot.review_sent")
        else:
            log.error("bot.review_failed")
            return
        # The review went out; the comment is an extra and never fails the job. A lost "key
        # stopped working" notice isn't sent again, but the Account page still shows it.
        try:
            comment = await ai_comment.weekly(me.sessions, self.settings, self._local_today())
            if comment is not None and not await send_with_retry(context.bot, me.chat, comment):
                log.warning("bot.ai_comment_not_sent")
        except Exception:
            log.exception("bot.ai_comment_failed")

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        """A morning-message button, acting on the presser's own queue: an id in forged data
        names nothing of anyone else's (ADR-0089)."""
        query = update.callback_query
        if query is None:
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
            with session_scope(me.sessions) as session:
                markup = buttons.pick(tid, queue_actions.choices(session))
            await query.answer()
            await edit_quietly(query.edit_message_reply_markup(keep(markup)))
            return
        if press.action == "start":
            with session_scope(me.sessions) as session:
                block = blocks.current(session, on, self.settings.tz)
                plan = session_plan(session, tid, block, on=on)
                shown = guided.at_length(session, on, plan) if plan is not None else None
            await query.answer()
            await reply(STALE if shown is None else session_detail_text(*shown))
            return

        # Actions that change the queue: one transaction, then retire the old buttons.
        with session_scope(me.sessions) as session:
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

    async def nudge(self, context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        """The evening message, unless paused: the nudge when it's on and nothing is logged
        today (not on a rest day, ADR-0091), and the habit buttons when they're on (D5). Both go
        in one message."""
        today = self._local_today()
        try:
            with session_scope(me.sessions) as session:
                prefs = user_settings.load(session)
                logged = user_settings.anything_logged(session, today)
                plan = todays_session(session, today, self.settings.tz)
                ticked = habits.checked(session, today)
        except SQLAlchemyError as exc:
            log.error("bot.nudge_failed", error=type(exc).__name__)
            return
        nudge = (
            not prefs.paused
            and prefs.nudges_enabled
            and not logged
            and plan is not None
            and (plan.test_day is not None or not plan.rest_day)
        )
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
        if await send_with_retry(
            context.bot,
            me.chat,
            "\n\n".join(parts),
            reply_markup=InlineKeyboardMarkup(rows),
        ):
            log.info("bot.nudge_sent", nudge=nudge, habits=bool(habit_rows))
        else:
            log.error("bot.nudge_failed")

    async def error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Log any handler failure (type only, never the message) and tell the person, if the
        gate let the update through for someone: never a stranger."""
        log.error("bot.handler_failed", error=type(context.error).__name__)
        if (
            isinstance(update, Update)
            and self.gate is not None
            and self.gate.person(update) is not None
            and update.effective_message is not None
        ):
            await update.effective_message.reply_text(SOMETHING_WENT_WRONG)


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
    if settings.telegram_allowed_user_id is None:  # the owner's account (users.link_owner)
        raise ValueError("TC_TELEGRAM_ALLOWED_USER_ID must be set to run the bot")
    # Only in a private chat: in a group, links and logs would be seen by everyone in it
    # (ADR-0040). The gate checks it too; a second look costs nothing.
    private = filters.ChatType.PRIVATE
    handlers = Handlers(settings)
    # Before every other handler: who it's from, and whether to serve them (ADR-0089, ADR-0085).
    gate = Gate(settings, unbound_like(sessions))
    handlers.gate = gate
    served = gate.served
    application.add_handler(TypeHandler(Update, gate.check), group=-1)
    progress_handlers = progress_ui.ProgressHandlers(settings)
    habit_handlers = habits_ui.HabitHandlers(settings)
    undo_handlers = undo_ui.UndoHandlers(settings)
    share_handlers = share_ui.ShareHandlers(settings)
    for names, callback in (
        (["start", "help"], handlers.help),
        (["today"], handlers.today),
        (["week"], handlers.week),
        (["login"], handlers.login),
        (["recover"], handlers.recover),
        (["progress"], progress_handlers.command),
        (["review"], progress_handlers.review),
        (["habits"], habit_handlers.command),
        (["undo"], undo_handlers.command),
        (["share"], share_handlers.command),
    ):
        application.add_handler(CommandHandler(names, served(callback), filters=private))
    stretch_handlers = stretching_ui.StretchHandlers(settings)
    application.add_handler(
        CallbackQueryHandler(served(stretch_handlers.button), pattern=rf"^{stretching_ui.PREFIX}:")
    )
    application.add_handler(
        CallbackQueryHandler(served(habit_handlers.button), pattern=rf"^{habits_ui.PREFIX}:")
    )
    application.add_handler(
        CallbackQueryHandler(served(handlers.button), pattern=rf"^{buttons.PREFIX}:")
    )
    daily_handlers = daily_ui.DailyCheckHandlers(settings)
    application.add_handler(
        CallbackQueryHandler(served(daily_handlers.button), pattern=rf"^{daily_ui.PREFIX}:")
    )
    band_handlers = band_ui.BandHandlers(settings, gate.everyone, send_with_retry)
    application.add_handler(
        CallbackQueryHandler(served(band_handlers.button), pattern=band_ui.PATTERN)
    )
    jobs = application.job_queue
    assert jobs is not None  # noqa: S101 - the job-queue extra is a dependency
    # Band workouts to count (ADR-0055): checked every few minutes, each offered once.
    jobs.run_repeating(band_handlers.announce, interval=band_ui.EVERY, name=band_ui.JOB)
    # And whether band data stopped arriving: checked hourly, told once per gap.
    jobs.run_repeating(band_handlers.watch, interval=band_ui.WATCH_EVERY, name=band_ui.WATCH_JOB)
    # Logs a connected AI proposed (ADR-0058): sent as they come, and checked every few
    # minutes for any whose send failed.
    proposal_handlers = proposals_ui.ProposalHandlers(settings, gate.everyone, send_outcome)
    application.add_handler(
        CallbackQueryHandler(served(proposal_handlers.button), pattern=proposals_ui.PATTERN)
    )
    jobs.run_repeating(proposal_handlers.job, interval=proposals_ui.EVERY, name=proposals_ui.JOB)

    # What a release changed in the plan (ADR-0087): told once.
    notice_handlers = notices_ui.NoticeHandlers(settings, gate.everyone, send_outcome)
    jobs.run_repeating(notice_handlers.job, interval=notices_ui.EVERY, name=notices_ui.JOB)

    async def announce(user_id: int) -> None:
        await proposal_handlers.announce(application.bot, user_id)

    application.bot_data[ANNOUNCE] = announce
    application.add_handler(
        CallbackQueryHandler(served(undo_handlers.button), pattern=rf"^{undo_ui.PREFIX}:")
    )

    # Each person's morning, nudge and review, at their own times (step 9).
    schedules = schedules_ui.Schedules(
        application,
        gate,
        {
            schedules_ui.MORNING: handlers.morning,
            schedules_ui.NUDGE: handlers.nudge,
            schedules_ui.REVIEW: handlers.weekly_review,
        },
    )
    # For times changed on the web (C6) and a member's Telegram connected (ADR-0089).
    application.bot_data[RESCHEDULE] = schedules.person
    settings_handlers = settings_ui.SettingsHandlers(settings, schedules.person)
    application.add_handler(
        CommandHandler("settings", served(settings_handlers.command), filters=private)
    )
    application.add_handler(
        CallbackQueryHandler(served(settings_handlers.button), pattern=rf"^{settings_ui.PREFIX}:")
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
    log_handlers = LogHandlers(settings, groq)
    # Everything kept in memory by user id, dropped on unlink, leave and erase (ADR-0089).
    for keeper in (log_handlers, band_handlers, proposal_handlers, settings_handlers):
        gate.keeps(keeper.forget)

    def forget(user_id: int) -> None:
        """Their state, and their jobs: gone with their link, or back at the default times
        after the owner's erase, which keeps it."""
        gate.forget(user_id)
        schedules.person(user_id)

    application.bot_data[FORGET] = forget
    application.add_handler(
        CallbackQueryHandler(served(log_handlers.button), pattern=rf"^{logging_flow.PREFIX}:")
    )
    application.add_handler(
        CallbackQueryHandler(served(progress_handlers.button), pattern=rf"^{progress_ui.PREFIX}:")
    )

    async def text(update: Update, context: ContextTypes.DEFAULT_TYPE, me: Person) -> None:
        """The one handler for plain text: PTB runs only the first match in a group. A pending
        /settings question gets the answer; anything else is a workout log (1-E)."""
        message = update.effective_message
        words = message is not None and any(c.isalpha() for c in message.text or "")
        if words:
            settings_handlers.awaiting.pop(me.user_id, None)  # a log, not a time: stop asking
        if me.user_id in settings_handlers.awaiting:
            await settings_handlers.typed_time(update, context, me)
        else:
            await log_handlers.message(update, context, me)

    text_only = filters.TEXT & ~filters.COMMAND & private
    application.add_handler(MessageHandler(text_only, served(text)))
    application.add_handler(MessageHandler(filters.VOICE & private, served(log_handlers.voice)))

    application.add_error_handler(handlers.error)

    schedules.everyone()
    log.info("bot.built")  # no Telegram id in the logs
    return application
