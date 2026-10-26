"""Workouts from the band, offered in Telegram (ADR-0055): "Walk, 46 min, 38 in zone 2 - count
it?" with Count it / Not this one.

A job looks for new offers every few minutes and sends each once. Callback data is
``bc:<import id>`` to count it or ``bx:<import id>`` to turn it down; the service re-checks the
import, so an old or forged button can't count anything that isn't offered. Counting one that
would complete a session on a day that already has one asks first (ADR-0060, ``bot.clash``),
with ``ba:<answer>:<import id>`` buttons.

A second job tells the person when band data stops arriving for a day, once per gap, and when
it arrives again; and, while it flows, when steps, sleep or heart rate alone stop for two days
(``domain.band_watch``). The messages carry no health values.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
from telegram.ext import ContextTypes

from training_coach.bot import clash as clash_ui
from training_coach.bot import links
from training_coach.bot.buttons import edit_quietly, row_id
from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain import band_watch
from training_coach.domain.band_watch import Feed, FeedNotices, Notice
from training_coach.domain.queue import local_date
from training_coach.services import band_cardio, cardio, ingest_keys, user_settings, workout_log
from training_coach.services.day_clash import MOVE, Clash, Refused, Resolution

log = structlog.get_logger(__name__)

COUNT, SKIP, ANSWER = "bc", "bx", "ba"
PATTERN = rf"^({COUNT}|{SKIP}|{ANSWER}):"
EVERY = timedelta(minutes=10)
JOB = "band.offers"
GONE = "That workout isn't on offer any more."
STALE = "Today's session changed meanwhile. Open Today in the app to count it."
SKIPPED = "Left out."
FAILED = "Couldn't save that just now. Try again, or count it on Today in the app."
NOT_COUNTED = "Not counted. It's still on offer."
WATCH_EVERY = timedelta(hours=1)
WATCH_JOB = "band.watch"
READER = "tc-reader/"  # the start of the coach's own reader's app_version (ADR-0070)
NOTICES = {
    Notice.QUIET: (
        "No band data has arrived for a day. Open Mi Fitness to sync the band, then the Coach "
        "reader, and tap Sync now. Band import: Account → Band import."
    ),
    Notice.EMPTY: (
        "The Coach reader is syncing, but nothing new has come from the band for a day. Open Mi "
        "Fitness to sync the band, and check that Mi Fitness still shares with Health Connect."
    ),
    Notice.BACK: "Band data is arriving again.",
}
# The same for a phone that still sends with HC Webhook (ADR-0055), told apart by its version.
WEBHOOK_NOTICES = {
    Notice.QUIET: (
        "No band data has arrived for a day. Open Mi Fitness to sync the band, and check HC "
        "Webhook's log. Band import: Account → Band import."
    ),
    Notice.EMPTY: (
        "HC Webhook is syncing, but nothing new has come from the band for a day. Open Mi "
        "Fitness to sync the band, and check that Mi Fitness still shares with Health Connect."
    ),
    Notice.BACK: "Band data is arriving again.",
}
FEED_NAMES = {Feed.STEPS: "step", Feed.SLEEP: "sleep", Feed.HEART_RATE: "heart-rate"}

Send = Callable[..., Awaitable[bool]]


def parse(data: str | None) -> tuple[str, int] | None:
    """What a button asks and the import it names, or None for anything malformed. An answer
    to the question comes back as its answer (``replace``, ``m3``...)."""
    parts = (data or "").split(":")
    if len(parts) == 3 and parts[0] == ANSWER and clash_ui.is_answer(parts[1]):
        found = row_id(parts[2])
        return (parts[1], found) if found is not None else None
    if len(parts) != 2 or parts[0] not in (COUNT, SKIP):
        return None
    found = row_id(parts[1])
    return (parts[0], found) if found is not None else None


def markup(offer: band_cardio.Offer | int) -> InlineKeyboardMarkup:
    offer_id = offer if isinstance(offer, int) else offer.id
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Count it", callback_data=f"{COUNT}:{offer_id}"),
                InlineKeyboardButton("Not this one", callback_data=f"{SKIP}:{offer_id}"),
            ]
        ]
    )


def _names(feeds: tuple[Feed, ...], joiner: str) -> str:
    names = [FEED_NAMES[feed] for feed in feeds]
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} {joiner} {names[-1]}"


def webhook(app_version: str | None) -> bool:
    """Whether the phone's last stored sync came from HC Webhook rather than the coach's own
    reader, from the version string it sent. Before any, the reader is assumed: it replaced
    HC Webhook (ADR-0070)."""
    return app_version is not None and not app_version.startswith(READER)


def feeds_text(notices: FeedNotices, from_webhook: bool = False) -> str:
    """The message for kinds of band data that stopped or came back."""
    lines = []
    if notices.stopped:
        where = (
            "In HC Webhook, check Data Types, and look under Sync Now for an error."
            if from_webhook
            else "In the Coach reader, tap Sync now: it says what it sent of each kind, or why "
            "it couldn't."
        )
        lines.append(
            f"No {_names(notices.stopped, 'or')} data has come from the band for two days, "
            f"though other band data has. {where}"
        )
    if notices.back:
        names = _names(notices.back, "and")
        verb = "is" if len(notices.back) == 1 else "are"
        lines.append(f"{names[0].upper()}{names[1:]} data {verb} arriving again.")
    return "\n\n".join(lines)


def counted_text(week: cardio.Week, planned: bool) -> str:
    done = "Counted, and today's session is done." if planned else "Counted."
    target = f" of {week.zone2_target[0]}-{week.zone2_target[1]}" if week.zone2_target else ""
    return f"{done} Zone 2 in the last 7 days: {week.zone2}{target} min. /undo takes it back."


class BandHandlers:
    def __init__(self, settings: Settings, sessions: sessionmaker[Session], send: Send) -> None:
        self.settings = settings
        self.sessions = sessions
        self.send = send
        # Import id -> the clash shown for it, and a day to move to found taken (ADR-0060).
        self.asked: dict[int, tuple[Clash, date | None]] = {}

    def _today(self) -> date:
        return local_date(datetime.now(UTC), self.settings.tz)

    async def announce(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send each new offer once, unless paused. An offer is marked sent only after Telegram
        took it, so a failed send is tried again on the next run (review of #226)."""
        try:
            with session_scope(self.sessions) as session:
                if user_settings.load(session).paused:
                    return
                found = band_cardio.unannounced(session, self._today())
        except SQLAlchemyError as exc:
            log.error("bot.band_offer_failed", error=type(exc).__name__)
            return
        owner = self.settings.telegram_allowed_user_id
        assert owner is not None  # noqa: S101 - owner_only
        bot: Bot = context.bot
        for offer in found:
            if not await self.send(bot, owner, offer.text, reply_markup=markup(offer)):
                log.warning("bot.band_offer_not_sent")
                return  # Telegram is unreachable; the rest wait for the next run too
            try:
                with session_scope(self.sessions) as session:
                    band_cardio.announced(session, offer.id, datetime.now(UTC))
            except SQLAlchemyError as exc:  # sent but not marked: stop, so nothing goes twice
                log.error("bot.band_offer_unmarked", error=type(exc).__name__)
                return
            log.info("bot.band_offer_sent")

    async def watch(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Tell the person when band data stopped a day ago, or one kind of it two days ago,
        or arrives again after that: in the day only (08:00-21:00 local), never while paused,
        and noted only after Telegram took it, so a failed send is tried again next run."""
        now = datetime.now(UTC)
        if not band_watch.daytime(now, self.settings.tz):
            return
        try:
            with session_scope(self.sessions) as session:
                if user_settings.load(session).paused:
                    return
                notice = ingest_keys.watch(session, now)
                feeds = ingest_keys.watch_feeds(session, now)
                from_webhook = webhook(ingest_keys.status(session).app_version)
        except SQLAlchemyError as exc:
            log.error("bot.band_watch_failed", error=type(exc).__name__)
            return
        if notice is not None:
            texts = WEBHOOK_NOTICES if from_webhook else NOTICES
            text, stopped, kind = texts[notice], notice is not Notice.BACK, notice.value
        elif feeds:
            text, stopped, kind = feeds_text(feeds, from_webhook), bool(feeds.stopped), "feeds"
        else:
            return
        owner = self.settings.telegram_allowed_user_id
        assert owner is not None  # noqa: S101 - owner_only
        account = links.with_open(None, self.settings.public_url, links.ACCOUNT)
        if not await self.send(context.bot, owner, text, reply_markup=account if stopped else None):
            log.warning("bot.band_watch_not_sent", notice=kind)
            return
        try:
            with session_scope(self.sessions) as session:
                if notice is not None:
                    ingest_keys.told(session, notice, now)
                else:
                    ingest_keys.told_feeds(session, feeds, now)
        except SQLAlchemyError as exc:  # sent but not noted: it may be sent again next hour
            log.error("bot.band_watch_unnoted", error=type(exc).__name__)
            return
        log.info("bot.band_watch_sent", notice=kind)

    async def button(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        """Count it or Not this one. Strangers get nothing, not even an answer (T1)."""
        query = update.callback_query
        user = update.effective_user
        if query is None or user is None or user.id != self.settings.telegram_allowed_user_id:
            return
        pressed = parse(query.data)
        if pressed is None or not isinstance(query.message, Message):
            await query.answer()
            return
        await query.answer()
        action, import_id = pressed
        today = self._today()
        asked = self.asked.get(import_id)
        keyboard: InlineKeyboardMarkup | None = None
        if action in ("cancel", MOVE) or (action not in (COUNT, SKIP) and asked is None):
            await edit_quietly(query.edit_message_reply_markup(None))
            if action == MOVE and asked is not None:
                days = clash_ui.days_keyboard(ANSWER, str(import_id), asked[0], today, asked[1])
                await query.message.reply_text(clash_ui.MOVE_ASK_BUTTONS, reply_markup=days)
            else:  # Cancel, or an answer to a question asked before a restart
                self.asked.pop(import_id, None)
                await query.message.reply_text(NOT_COUNTED, reply_markup=markup(import_id))
            return
        answer = clash_ui.resolution(action, asked[0], today) if asked is not None else None
        try:
            with session_scope(self.sessions) as session:
                if action == SKIP:
                    band_cardio.dismiss(session, import_id)
                    reply = SKIPPED
                else:
                    result = band_cardio.count(session, import_id, today, self.settings.tz, answer)
                    if isinstance(result, band_cardio.Gone):
                        reply = GONE
                    elif isinstance(result, workout_log.Stale):
                        reply = STALE
                    elif isinstance(result, Clash | Refused):
                        reply, keyboard = self._ask(import_id, result, answer, today)
                    else:
                        reply = counted_text(cardio.week(session, today), result.planned)
        except SQLAlchemyError as exc:  # keep the buttons, so it can be pressed again
            log.error("bot.band_offer_failed", error=type(exc).__name__)
            await query.message.reply_text(FAILED)
            return
        if keyboard is None:
            self.asked.pop(import_id, None)
        await edit_quietly(query.edit_message_reply_markup(None))
        await query.message.reply_text(reply, reply_markup=keyboard)
        log.info("bot.band_offer_answered", action=action)

    def _ask(
        self, import_id: int, result: Clash | Refused, answer: Resolution | None, today: date
    ) -> tuple[str, InlineKeyboardMarkup]:
        """The question (again), or the days to move to when the one picked was taken."""
        shown = self.asked.get(import_id)
        ref = str(import_id)
        if shown is not None and (isinstance(result, Refused) or result.moving):
            taken = result.day if isinstance(result, Clash) else shown[1]
            self.asked[import_id] = (shown[0], taken)
            days = clash_ui.days_keyboard(ANSWER, ref, shown[0], today, taken)
            why = clash_ui.taken_text(result) if isinstance(result, Clash) else result.reason
            return f"{why}\n\n{clash_ui.MOVE_ASK_BUTTONS}", days
        assert isinstance(result, Clash)  # noqa: S101 - a refusal only answers a move
        self.asked[import_id] = (result, None)
        reply = clash_ui.text(result)
        if answer is not None:
            reply = f"{clash_ui.CHANGED}\n\n{reply}"
        return reply, clash_ui.keyboard(ANSWER, ref, len(result.recorded) == 1)
