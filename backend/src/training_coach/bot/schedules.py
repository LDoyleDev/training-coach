"""Each person's scheduled messages (step 9, the multi-user plan's F1): named jobs per person,
``morning:<user id>``, ``nudge:<user id>`` and ``weekly-review:<user id>``, at the times in
their own settings. The times carry the timezone, so a job follows DST: 07:30 stays 07:30 local.

They are made at start-up for everyone with Telegram linked whom the switch lets in (ADR-0059),
and made again when a member connects Telegram and when the person changes a time in /settings
or on the web. Unlink, leave, removal and erase take them away, with ``Gate.forget``; the
owner's erase keeps the link, so theirs start again at the default times. Each run asks the gate
whom it is for (``Gate.scheduled``): nothing goes to someone unlinked, closed out by the switch
or away (ADR-0085), and the message goes to the chat they are linked to now, read with sessions
bound to them.
"""

from collections.abc import Callable, Coroutine
from datetime import time
from typing import Any

import structlog
from sqlalchemy.exc import SQLAlchemyError
from telegram.ext import Application, ContextTypes, JobQueue

from training_coach.bot.gate import Gate, Person
from training_coach.db.session import session_scope
from training_coach.services import user_settings, users
from training_coach.services.user_settings import Prefs

log = structlog.get_logger(__name__)

MORNING, NUDGE, REVIEW = "morning", "nudge", "weekly-review"
KINDS = (MORNING, NUDGE, REVIEW)
EVERY_DAY = tuple(range(7))
SUNDAY = 0  # PTB counts days from Sunday (0) to Saturday (6)

Send = Callable[[ContextTypes.DEFAULT_TYPE, Person], Coroutine[Any, Any, None]]


def name(kind: str, user_id: int) -> str:
    """A person's job: ``morning:2``. Ids are never handed out twice (ADR-0088 addendum)."""
    return f"{kind}:{user_id}"


class Schedules:
    def __init__(
        self,
        application: Application,  # type: ignore[type-arg]  # see bot.app.build_bot
        gate: Gate,
        sends: dict[str, Send],
    ) -> None:
        self.application = application
        self.gate = gate
        self.sends = sends  # what each kind of job sends, given the person

    def _queue(self) -> JobQueue:  # type: ignore[type-arg]  # see bot.app.build_bot
        queue = self.application.job_queue
        assert queue is not None  # noqa: S101 - the job-queue extra is a dependency
        return queue

    def everyone(self) -> None:
        """At start-up: the jobs of everyone with Telegram linked. If that can't be read, the
        owner's at least, as start-up just linked them."""
        try:
            with session_scope(self.gate.shared) as session:
                linked = users.linked(session)
        except SQLAlchemyError as exc:  # don't block start-up (ADR-0015 spirit)
            log.error("bot.linked_unreadable", error=type(exc).__name__)
            linked = [users.OWNER]
        for user_id in linked:
            self.person(user_id)

    def person(self, user_id: int) -> None:
        """Make ``user_id``'s jobs again from their settings now, or take them away if they
        have no Telegram linked or the switch closes the app to them. If that can't be read,
        the jobs they have stay as they are (the next change or restart reads it again), and
        someone with none, at start-up, gets the default times; each run checks whom it is for
        anyway."""
        if users.closed_to(user_id, self.gate.settings.multi_user):
            self.drop(user_id)
            return
        try:
            with session_scope(self.gate.shared) as session:
                chat = users.telegram_chat(session, user_id)
            if chat is None:
                self.drop(user_id)
                return
            with session_scope(self.gate.sessions_for(user_id)) as session:
                prefs = user_settings.load(session)
        except SQLAlchemyError as exc:
            log.error("bot.settings_unreadable", error=type(exc).__name__)
            if self._has(user_id):
                return
            prefs = Prefs()
        self.drop(user_id)
        self._daily(MORNING, user_id, prefs.morning_time, EVERY_DAY)
        self._daily(NUDGE, user_id, prefs.nudge_time, EVERY_DAY)
        self._daily(REVIEW, user_id, prefs.review_time, (SUNDAY,))

    def _has(self, user_id: int) -> bool:
        return any(self._queue().get_jobs_by_name(name(kind, user_id)) for kind in KINDS)

    def drop(self, user_id: int) -> None:
        for kind in KINDS:
            for job in self._queue().get_jobs_by_name(name(kind, user_id)):
                job.schedule_removal()

    def _daily(self, kind: str, user_id: int, at: time, days: tuple[int, ...]) -> None:
        send = self.sends[kind]

        async def run(context: ContextTypes.DEFAULT_TYPE) -> None:
            me = self.gate.scheduled(user_id)
            if me is None:  # unlinked, closed out or away: nothing scheduled goes
                log.info("bot.job_skipped", job=kind)
                return
            await send(context, me)

        tz = self.gate.settings.tz
        job = name(kind, user_id)
        self._queue().run_daily(run, time=at.replace(tzinfo=tz), days=days, name=job)
        log.info("bot.job_scheduled", job=job, at=at.isoformat())
