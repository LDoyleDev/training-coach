"""Groq client: speech-to-text for voice logs and the log-rewrite fallback (ADR-0008).

Every call has a timeout, transient failures (timeouts, connection errors, 5xx) are retried
with backoff, and anything else becomes ``GroqUnavailableError`` so the bot can ask the user to
type the log instead. Transcripts are returned to the caller and never logged here.
"""

import asyncio
import json
import re
import unicodedata
from importlib.resources import files as package_files
from typing import Annotated, Any, Literal

import httpx
import structlog
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

log = structlog.get_logger(__name__)

BASE_URL = "https://api.groq.com/openai/v1"
LOG_TAG = re.compile(r"<\s*/?\s*log\s*>", re.IGNORECASE)
PROMPT_CHARS = 800  # Whisper takes up to 224 tokens of prompt; stay well under


class GroqUnavailableError(Exception):
    """Groq could not answer: rate limited, down, or returned something unusable."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _Transcript(BaseModel):
    text: str


class RewriteLine(BaseModel):
    """One exercise as the model read it. Untrusted: re-parsed by the rule parser."""

    model_config = ConfigDict(extra="forbid")
    exercise: str = Field(max_length=120)
    sets: list[Annotated[int, Field(ge=0)]] = Field(max_length=20)
    unit: Literal["", "s", "min"]


class Rewrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lines: list[RewriteLine] = Field(max_length=30)


def _rewrite_schema(names: list[str]) -> dict[str, Any]:
    """Strict JSON schema: exercise names are an enum of the plan's names."""
    line = {
        "type": "object",
        "properties": {
            "exercise": {"type": "string", "enum": names},
            "sets": {"type": "array", "items": {"type": "integer"}},
            "unit": {"type": "string", "enum": ["", "s", "min"]},
        },
        "required": ["exercise", "sets", "unit"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"lines": {"type": "array", "items": line}},
        "required": ["lines"],
        "additionalProperties": False,
    }


def rewrite_prompt() -> str:
    return package_files("training_coach.prompts").joinpath("log_rewrite.md").read_text("utf-8")


class GroqClient:
    def __init__(
        self,
        api_key: SecretStr,
        *,
        transcribe_model: str = "whisper-large-v3-turbo",
        parse_model: str = "openai/gpt-oss-20b",
        timeout: float = 20.0,
        attempts: int = 3,
        backoff: float = 1.0,
        deadline: float = 45.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._key = api_key
        self._model = transcribe_model
        self._parse_model = parse_model
        self._timeout = timeout
        self._attempts = attempts
        self._backoff = backoff
        self._deadline = deadline  # the whole call, retries included: the owner is waiting
        self._transport = transport

    async def transcribe(self, audio: bytes, *, vocabulary: list[str]) -> str:
        """Text of a voice note. ``vocabulary`` (exercise names) steers Whisper's spelling."""
        prompt = ", ".join(vocabulary)[:PROMPT_CHARS]
        data = {"model": self._model, "language": "en", "response_format": "json"}
        if prompt:
            data["prompt"] = prompt
        files = {"file": ("voice.ogg", audio, "audio/ogg")}
        try:
            async with asyncio.timeout(self._deadline):
                response = await self._post("/audio/transcriptions", data=data, files=files)
        except TimeoutError as exc:
            log.warning("groq.deadline", path="/audio/transcriptions")
            raise GroqUnavailableError("timeout") from exc
        try:
            return _Transcript.model_validate(response.json()).text.strip()
        except (ValueError, ValidationError) as exc:
            raise GroqUnavailableError("bad_response") from exc

    async def rewrite_log(self, text: str, *, names: list[str]) -> Rewrite:
        """The model's reading of a log the rule parser couldn't. Never trusted as data: no
        tools, a strict schema, and the caller re-parses the result with the rule parser."""
        # The log is delimited as data; don't let it open or close the delimiter itself,
        # in any case, spacing or Unicode look-alike (NFKC folds full-width brackets).
        text = LOG_TAG.sub(" ", unicodedata.normalize("NFKC", text))
        body = {
            "model": self._parse_model,
            "temperature": 0,
            "max_completion_tokens": 1000,
            "messages": [
                {"role": "system", "content": rewrite_prompt()},
                {
                    "role": "user",
                    "content": f"Exercises: {json.dumps(names)}\n\n<log>\n{text}\n</log>",
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "workout_log",
                    "strict": True,
                    "schema": _rewrite_schema(names),
                },
            },
        }
        try:
            async with asyncio.timeout(self._deadline):
                response = await self._post("/chat/completions", json_body=body)
        except TimeoutError as exc:
            log.warning("groq.deadline", path="/chat/completions")
            raise GroqUnavailableError("timeout") from exc
        try:
            content = response.json()["choices"][0]["message"]["content"]
            rewrite = Rewrite.model_validate_json(content)
        except (ValueError, KeyError, IndexError, TypeError, ValidationError) as exc:
            raise GroqUnavailableError("bad_response") from exc
        # Enforce the schema's enum here too, in case the provider or model ignores it: a
        # name with a separator in it could smuggle in an extra line.
        if any(line.exercise not in names for line in rewrite.lines):
            raise GroqUnavailableError("bad_response")
        return rewrite

    async def _post(
        self,
        path: str,
        *,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self._key.get_secret_value()}"}
        async with httpx.AsyncClient(
            base_url=BASE_URL, timeout=self._timeout, transport=self._transport
        ) as client:
            for attempt in range(1, self._attempts + 1):
                try:
                    response = await client.post(
                        path, data=data, files=files, json=json_body, headers=headers
                    )
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
