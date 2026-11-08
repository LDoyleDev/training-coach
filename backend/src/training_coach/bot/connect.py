"""The bot's half of connecting a member's Telegram (ADR-0089): ``/start <token>`` from someone
not linked yet. It is the one thing a stranger reaches, only while ``TC_MULTI_USER`` is on, and
the sender gate answers it itself, so nothing else runs for them.

It connects nothing: the sender is recorded as a claim on the link and gets a 6-digit code to
type on the Account page, where the member confirms (``services.telegram_link``). At most 5 a
sender and 30 overall in 10 minutes; over that, no reply. Tokens, codes and Telegram ids are
never logged.
"""

import re
import time
from datetime import UTC, datetime

import structlog
from sqlalchemy.orm import Session, sessionmaker
from telegram import Update

from training_coach.config import Settings
from training_coach.db.session import session_scope
from training_coach.domain.rate_limit import RateLimit
from training_coach.services import telegram_link

log = structlog.get_logger(__name__)

PER_SENDER, OVERALL, WINDOW = 5, 30, 600.0
TOKEN = re.compile(r"[A-Za-z0-9_-]{20,100}")  # token_urlsafe(32) is 43 characters
CODE_TEXT = (
    "Your code: {code}\n\n"
    "Type it on the Account page, in the browser where you tapped Connect Telegram. It works "
    "for 10 minutes. Never give it to anyone else."
)
EXPIRED_TEXT = (
    "This link has expired or was used. Make a new one on the Account page in Training Coach."
)


def start_token(update: Update) -> str | None:
    """The token of a ``/start <token>`` message, the way a t.me link sends it; None for
    anything else."""
    message = update.message
    parts = (message.text or "").split() if message is not None else []
    if len(parts) != 2 or parts[0] != "/start" or not TOKEN.fullmatch(parts[1]):
        return None
    return parts[1]


class Connect:
    def __init__(self, settings: Settings, shared: sessionmaker[Session]) -> None:
        self.settings = settings
        self.shared = shared  # unbound: the token says whose link it is
        self.per_sender = RateLimit(PER_SENDER, WINDOW)
        self.overall = RateLimit(OVERALL, WINDOW)

    def claim(self, telegram_user_id: int, name: str, token: str) -> str | None:
        """What to reply to a stranger's ``/start <token>``: their code, or that the link is no
        good. None when over the limits: then nothing is said."""
        now = time.monotonic()
        if not self.per_sender.allow(str(telegram_user_id), now) or not self.overall.allow(
            "all", now
        ):
            log.info("bot.connect_limited")
            return None
        with session_scope(self.shared) as session:
            found = telegram_link.claim(
                session,
                token,
                telegram_user_id,
                name,
                datetime.now(UTC),
                configured=self.settings.telegram_allowed_user_id,
            )
        log.info("bot.connect_claim", claimed=found is not None)
        return CODE_TEXT.format(code=found.code) if found is not None else EXPIRED_TEXT
