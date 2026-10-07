"""Application settings, loaded from environment variables (prefix ``TC_``) or ``.env``.

Secrets are typed as ``SecretStr`` so they never appear in logs or reprs.
See ``.env.example`` for every variable and ``docs/runbooks/rotate-secrets.md``.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal
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

    # Scheduling
    timezone: str = "Europe/Berlin"

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def bot_enabled(self) -> bool:
        return self.telegram_bot_token is not None and self.telegram_allowed_user_id is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
