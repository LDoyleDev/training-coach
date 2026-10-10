"""Encryption for secrets people store in the app, like their own Groq key (ADR-0047 B).

Fernet (AES-128-CBC with HMAC-SHA256) under ``TC_SECRETS_KEY``: one or more keys, newest first.
New secrets are sealed with the newest; any listed key opens them, so a key can be rotated by
adding a new one, re-sealing (``rotate-secrets``) and then removing the old one.

This protects a leaked database or backup, not a compromised Pi: the key sits in ``.env`` on
the same host. Plaintext never leaves this module except to the caller that needs it.
"""

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from pydantic import SecretStr

from training_coach.config import fernet_keys


class SecretBox:
    def __init__(self, keys: SecretStr) -> None:
        listed = fernet_keys(keys.get_secret_value())
        if not listed:
            raise ValueError("no valid Fernet key")
        self._fernet = MultiFernet([Fernet(k) for k in listed])

    def seal(self, secret: str) -> bytes:
        return self._fernet.encrypt(secret.encode())

    def open(self, token: bytes) -> SecretStr | None:
        """The secret, or None when no listed key opens it (lost or removed key, tampering)."""
        try:
            return SecretStr(self._fernet.decrypt(token).decode())
        except InvalidToken:
            return None

    def rotate(self, token: bytes) -> bytes | None:
        """The same secret sealed with the newest key, or None when it can't be opened."""
        try:
            return self._fernet.rotate(token)
        except InvalidToken:
            return None
