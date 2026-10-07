"""Groq client: speech-to-text for voice logs (ADR-0008).

Every call has a timeout, transient failures (timeouts, connection errors, 5xx) are retried
with backoff, and anything else becomes ``GroqUnavailableError`` so the bot can ask the user to
type the log instead. Transcripts are returned to the caller and never logged here.
"""

import asyncio

import httpx
import structlog
from pydantic import BaseModel, SecretStr, ValidationError

log = structlog.get_logger(__name__)

BASE_URL = "https://api.groq.com/openai/v1"
PROMPT_CHARS = 800  # Whisper takes up to 224 tokens of prompt; stay well under


class GroqUnavailableError(Exception):
    """Groq could not answer: rate limited, down, or returned something unusable."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _Transcript(BaseModel):
    text: str


class GroqClient:
    def __init__(
        self,
        api_key: SecretStr,
        *,
        transcribe_model: str = "whisper-large-v3-turbo",
        timeout: float = 20.0,
        attempts: int = 3,
        backoff: float = 1.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._key = api_key
        self._model = transcribe_model
        self._timeout = timeout
        self._attempts = attempts
        self._backoff = backoff
        self._transport = transport

    async def transcribe(self, audio: bytes, *, vocabulary: list[str]) -> str:
        """Text of a voice note. ``vocabulary`` (exercise names) steers Whisper's spelling."""
        prompt = ", ".join(vocabulary)[:PROMPT_CHARS]
        data = {"model": self._model, "language": "en", "response_format": "json"}
        if prompt:
            data["prompt"] = prompt
        files = {"file": ("voice.ogg", audio, "audio/ogg")}
        response = await self._post("/audio/transcriptions", data=data, files=files)
        try:
            return _Transcript.model_validate(response.json()).text.strip()
        except (ValueError, ValidationError) as exc:
            raise GroqUnavailableError("bad_response") from exc

    async def _post(
        self, path: str, *, data: dict[str, str], files: dict[str, tuple[str, bytes, str]]
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._key.get_secret_value()}"}
        async with httpx.AsyncClient(
            base_url=BASE_URL, timeout=self._timeout, transport=self._transport
        ) as client:
            for attempt in range(1, self._attempts + 1):
                try:
                    response = await client.post(path, data=data, files=files, headers=headers)
                except httpx.TransportError as exc:  # includes timeouts
                    reason = type(exc).__name__
                else:
                    if response.status_code == httpx.codes.OK:
                        return response
                    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                        # Free-tier limits are per minute, hour and day; don't hammer them.
                        log.warning("groq.rate_limited", path=path)
                        raise GroqUnavailableError("rate_limited")
                    if response.status_code < 500:
                        log.warning("groq.rejected", path=path, status=response.status_code)
                        raise GroqUnavailableError(f"http_{response.status_code}")
                    reason = f"http_{response.status_code}"
                log.warning("groq.retry", path=path, attempt=attempt, reason=reason)
                if attempt < self._attempts:
                    await asyncio.sleep(self._backoff * 2 ** (attempt - 1))
        raise GroqUnavailableError("unreachable")
