import json

import httpx
import pytest
import respx
from pydantic import SecretStr
from structlog.testing import capture_logs

from training_coach.services.groq import BASE_URL, GroqClient, GroqUnavailableError

URL = f"{BASE_URL}/audio/transcriptions"
KEY = SecretStr("gsk_TEST-KEY")


def client() -> GroqClient:
    return GroqClient(KEY, backoff=0)


@respx.mock
async def test_transcribes_with_key_model_and_vocabulary() -> None:
    route = respx.post(URL).respond(json={"text": " pull-ups 8 8 7 "})
    text = await client().transcribe(b"OggS...", vocabulary=["Pull-up", "Dip"])
    assert text == "pull-ups 8 8 7"
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer gsk_TEST-KEY"
    body = request.content.decode("latin-1")
    assert 'name="model"' in body
    assert "whisper-large-v3-turbo" in body
    assert "Pull-up, Dip" in body
    assert 'filename="voice.ogg"' in body


@respx.mock
async def test_long_vocabulary_is_trimmed() -> None:
    route = respx.post(URL).respond(json={"text": "ok"})
    await client().transcribe(b"x", vocabulary=["word"] * 1000)
    assert route.calls.last.request.content.decode("latin-1").count("word") < 200


@respx.mock
async def test_transient_failures_are_retried() -> None:
    route = respx.post(URL).mock(
        side_effect=[
            httpx.ConnectTimeout("slow"),
            httpx.Response(503),
            httpx.Response(200, json={"text": "dips 10"}),
        ]
    )
    assert await client().transcribe(b"x", vocabulary=[]) == "dips 10"
    assert route.call_count == 3


@respx.mock
async def test_gives_up_after_the_last_attempt() -> None:
    respx.post(URL).mock(side_effect=httpx.ConnectError("down"))
    with pytest.raises(GroqUnavailableError, match="unreachable"):
        await client().transcribe(b"x", vocabulary=[])


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (httpx.Response(429, headers={"retry-after": "60"}), "rate_limited"),
        (httpx.Response(401), "http_401"),
        (httpx.Response(413), "http_413"),
        (httpx.Response(200, text="not json"), "bad_response"),
        (httpx.Response(200, json={"no": "text"}), "bad_response"),
    ],
)
async def test_unusable_answers_become_unavailable(response: httpx.Response, reason: str) -> None:
    with respx.mock:
        route = respx.post(URL).mock(return_value=response)
        with pytest.raises(GroqUnavailableError) as exc:
            await client().transcribe(b"x", vocabulary=[])
    assert exc.value.reason == reason
    assert route.call_count == 1  # never retried: rate limits and rejections won't improve


@respx.mock
async def test_transcripts_and_keys_never_reach_the_logs() -> None:
    respx.post(URL).mock(
        side_effect=[httpx.Response(500), httpx.Response(200, json={"text": "secret words 8"})]
    )
    with capture_logs() as logs:
        await client().transcribe(b"x", vocabulary=[])
    dumped = json.dumps(logs)
    assert "secret words" not in dumped
    assert "gsk_" not in dumped
    assert [entry["event"] for entry in logs] == ["groq.retry"]
