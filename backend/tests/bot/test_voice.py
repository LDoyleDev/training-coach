import json
from collections.abc import Callable

import httpx
import pytest
import respx
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from structlog.testing import capture_logs
from telegram.ext import Application

from tests.bot.fakes import AUDIO, OWNER, SETTINGS, STRANGER, button_data, run, texts, voice
from training_coach.bot.app import build_bot
from training_coach.bot.messages import VOICE_FAILED, VOICE_OFF, VOICE_TOO_LONG, heard_text
from training_coach.db.models import Workout
from training_coach.services.groq import BASE_URL, GroqClient

App = Application  # type: ignore[type-arg]  # see build_bot
Sessions = sessionmaker[Session]
GROQ = f"{BASE_URL}/audio/transcriptions"


@pytest.fixture
def voiced(seeded: Sessions) -> App:
    return build_bot(SETTINGS, seeded, GroqClient(SecretStr("gsk_TEST-KEY"), backoff=0))


def groq_says(response: httpx.Response) -> Callable[[respx.Router], None]:
    def add(router: respx.Router) -> None:
        router.post(GROQ).mock(return_value=response)

    return add


def _workouts(sessions: Sessions) -> int:
    with sessions() as session:
        return session.scalar(select(func.count()).select_from(Workout)) or 0


async def test_a_voice_note_becomes_a_log_to_confirm(voiced: App, seeded: Sessions) -> None:
    calls = await run(
        voiced,
        voice(OWNER),
        routes=groq_says(httpx.Response(200, json={"text": "Pull ups 8 8 7, dips 12"})),
    )
    (reply,) = texts(calls)
    assert reply.startswith('I heard: "Pull ups 8 8 7, dips 12"')
    assert "- Pull-up: 8 / 8 / 7" in reply
    assert [d.split(":")[1] for d in button_data(calls["sendMessage"][0])] == [
        "save",
        "edit",
        "cancel",
    ]
    assert _workouts(seeded) == 0  # still nothing saved without Save (ADR-0007)


async def test_the_audio_is_sent_with_exercise_names_as_vocabulary(voiced: App) -> None:
    seen: list[httpx.Request] = []

    def add(router: respx.Router) -> None:
        def record(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json={"text": "dips 10"})

        router.post(GROQ).mock(side_effect=record)

    await run(voiced, voice(OWNER), routes=add)
    body = seen[0].content
    assert AUDIO in body
    assert b"Pull-up" in body


@pytest.mark.parametrize(
    "response",
    [httpx.Response(429), httpx.Response(500), httpx.Response(200, json={"text": "  "})],
    ids=["rate-limited", "down", "silence"],
)
async def test_when_groq_cannot_help_the_owner_is_asked_to_type(
    voiced: App, response: httpx.Response
) -> None:
    calls = await run(voiced, voice(OWNER), routes=groq_says(response))
    assert texts(calls) == [VOICE_FAILED]


async def test_without_a_key_voice_is_off(application: App) -> None:
    assert texts(await run(application, voice(OWNER))) == [VOICE_OFF]


@pytest.mark.parametrize(("seconds", "size"), [(121, 20_000), (30, 6 * 1024 * 1024)])
async def test_long_voice_notes_are_refused_before_download(
    voiced: App, seconds: int, size: int
) -> None:
    calls = await run(voiced, voice(OWNER, seconds=seconds, size=size))
    assert texts(calls) == [VOICE_TOO_LONG]
    assert "getFile" not in calls


async def test_strangers_voice_notes_are_ignored(voiced: App) -> None:
    calls = await run(
        voiced,
        voice(STRANGER),
        routes=groq_says(httpx.Response(200, json={"text": "dips 10"})),
    )
    assert calls == {}


async def test_the_transcript_is_never_logged(voiced: App) -> None:
    with capture_logs() as logs:
        await run(
            voiced,
            voice(OWNER),
            routes=groq_says(httpx.Response(200, json={"text": "dips 10 private words"})),
        )
    dumped = json.dumps(logs, default=str)
    assert "private words" not in dumped
    assert "gsk_" not in dumped


def test_heard_text_is_short_and_printable() -> None:
    text = heard_text("\x00\x1b[31m" + "word " * 200)
    assert len(text) < 330
    assert "\x1b" not in text
    assert text.endswith('..."')
