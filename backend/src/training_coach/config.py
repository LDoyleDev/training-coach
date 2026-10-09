"""Application settings, loaded from environment variables (prefix ``TC_``) or ``.env``.

Secrets are typed as ``SecretStr`` so they never appear in logs or reprs.
See ``.env.example`` for every variable and ``docs/runbooks/rotate-secrets.md``.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # `TC_X=` in .env means "not set", never an empty value
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Storage
    database_url: str = "sqlite:///./data/training_coach.db"

    # Built dashboard (frontend/dist). Served at / when set; the Docker image sets it.
    web_dist_dir: Path | None = None

    # Telegram (phase 1). The bot only starts when a token is configured.
    telegram_bot_token: SecretStr | None = None
    telegram_allowed_user_id: int | None = Field(
        default=None,
        description="The only Telegram user ID the bot will respond to (ADR-0009).",
    )

    # Groq (transcription + fallback parsing, ADR-0008). Voice logs are off until a key is set.
    groq_api_key: SecretStr | None = None
    groq_transcribe_model: str = "whisper-large-v3-turbo"
    groq_parse_model: str = "openai/gpt-oss-20b"  # needs strict JSON-schema output

    # Scheduling
    timezone: str = "Europe/Berlin"

    # The web app's public address (https://coach.example.com). Sign-in links and the
    # passkey domain come from it (ADR-0036); web sign-in is off until it is set.
    public_url: str | None = None
    # Peers whose CF-Connecting-IP is believed (the Cloudflare tunnel's side): loopback and
    # Docker's bridge range. Not home networks (192.168.x), so a LAN host can't forge it.
    trusted_proxies: list[str] = ["127.0.0.0/8", "::1/128", "172.16.0.0/12"]

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value

    @field_validator("public_url")
    @classmethod
    def _https(cls, value: str | None) -> str | None:
        """An origin only (links append /signin#token), and https unless it is this machine."""
        if value is None:
            return None
        url = urlsplit(value.rstrip("/"))
        local = url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1"}
        if not (url.scheme == "https" or local) or not url.hostname:
            raise ValueError("public_url must be https (or http://localhost for development)")
        if url.path or url.query or url.fragment or url.username or url.password:
            raise ValueError("public_url is an origin only, like https://coach.example.com")
        return f"{url.scheme}://{url.netloc}"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def bot_enabled(self) -> bool:
        return self.telegram_bot_token is not None and self.telegram_allowed_user_id is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
