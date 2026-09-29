"""Training Coach: self-hosted training coach (Telegram bot, logging, dashboard API)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("training-coach")
except PackageNotFoundError:  # pragma: no cover - only when running from an uninstalled tree
    __version__ = "0.0.0"

__all__ = ["__version__"]
