"""A software passkey device for tests: it answers WebAuthn ceremonies as a phone would, with a
real P-256 key, so the server's checks run for real (the `webauthn` library verifies them).

``user_verified`` False plays a device that only checked presence (a tap, no fingerprint).
"""

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from typing import Any

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

UP, UV, AT = 0x01, 0x04, 0x40  # authenticator data flags: present, verified, attested data


def _b64(data: bytes) -> str:
    return bytes_to_base64url(data)


@dataclass
class Device:
    origin: str
    rp_id: str
    user_verified: bool = True
    key: ec.EllipticCurvePrivateKey = field(
        default_factory=lambda: ec.generate_private_key(ec.SECP256R1())
    )
    credential_id: bytes = field(default_factory=lambda: secrets.token_bytes(32))
    count: int = 0
    user_handle: bytes = b""

    def _client_data(self, kind: str, challenge: str, origin: str | None = None) -> bytes:
        data = {
            "type": kind,
            "challenge": challenge,
            "origin": origin or self.origin,
            "crossOrigin": False,
        }
        return json.dumps(data).encode()

    def _flags(self) -> int:
        return UP | (UV if self.user_verified else 0)

    def _cose_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps(
            {
                1: 2,
                3: -7,
                -1: 1,
                -2: numbers.x.to_bytes(32, "big"),
                -3: numbers.y.to_bytes(32, "big"),
            }
        )

    def register(self, options: dict[str, Any], origin: str | None = None) -> dict[str, Any]:
        """The answer to registration options: a new credential with "none" attestation."""
        self.user_handle = base64url_to_bytes(options["user"]["id"])
        auth_data = (
            hashlib.sha256(options["rp"]["id"].encode()).digest()
            + bytes([self._flags() | AT])
            + self.count.to_bytes(4, "big")
            + bytes(16)  # AAGUID
            + len(self.credential_id).to_bytes(2, "big")
            + self.credential_id
            + self._cose_key()
        )
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        client = self._client_data("webauthn.create", options["challenge"], origin)
        return {
            "id": _b64(self.credential_id),
            "rawId": _b64(self.credential_id),
            "type": "public-key",
            "response": {"clientDataJSON": _b64(client), "attestationObject": _b64(attestation)},
            "clientExtensionResults": {},
        }

    def sign_in(self, options: dict[str, Any], origin: str | None = None) -> dict[str, Any]:
        """The answer to sign-in options: a signed assertion with a higher counter."""
        self.count += 1
        auth_data = (
            hashlib.sha256(options["rpId"].encode()).digest()
            + bytes([self._flags()])
            + self.count.to_bytes(4, "big")
        )
        client = self._client_data("webauthn.get", options["challenge"], origin)
        signature = self.key.sign(
            auth_data + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256())
        )
        return {
            "id": _b64(self.credential_id),
            "rawId": _b64(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": _b64(client),
                "authenticatorData": _b64(auth_data),
                "signature": _b64(signature),
                "userHandle": _b64(self.user_handle),
            },
            "clientExtensionResults": {},
        }
