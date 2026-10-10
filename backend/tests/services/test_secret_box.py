"""Encryption for stored keys (ADR-0047 B)."""

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError

from training_coach.config import Settings, fernet_keys
from training_coach.services.secret_box import SecretBox

OLD = Fernet.generate_key().decode()
NEW = Fernet.generate_key().decode()


def test_a_sealed_secret_opens_and_is_not_in_the_clear() -> None:
    box = SecretBox(SecretStr(NEW))
    token = box.seal("gsk_secret_value")
    assert b"gsk_secret_value" not in token
    opened = box.open(token)
    assert opened is not None
    assert opened.get_secret_value() == "gsk_secret_value"


def test_another_key_cannot_open_it() -> None:
    token = SecretBox(SecretStr(OLD)).seal("x")
    assert SecretBox(SecretStr(NEW)).open(token) is None
    assert SecretBox(SecretStr(NEW)).rotate(token) is None


def test_rotation_moves_secrets_to_the_newest_key() -> None:
    token = SecretBox(SecretStr(OLD)).seal("x")
    both = SecretBox(SecretStr(f"{NEW}, {OLD}"))
    rotated = both.rotate(token)
    assert rotated is not None
    opened = SecretBox(SecretStr(NEW)).open(rotated)  # the old key can now be removed
    assert opened is not None
    assert opened.get_secret_value() == "x"


@pytest.mark.parametrize("value", ["", " , ", "not-a-key", f"{NEW},nope"])
def test_anything_but_fernet_keys_is_refused(value: str) -> None:
    assert fernet_keys(value) == []
    with pytest.raises(ValueError, match="no valid Fernet key"):
        SecretBox(SecretStr(value))


def test_settings_refuse_a_bad_key_without_repeating_it() -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(environment="test", secrets_key=SecretStr("my-very-secret-but-wrong"))
    assert "my-very-secret-but-wrong" not in str(caught.value)
    assert Settings(environment="test", secrets_key=SecretStr(NEW)).secrets_key is not None
