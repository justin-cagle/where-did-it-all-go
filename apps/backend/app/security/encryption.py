"""Field-level encryption using Fernet (symmetric AEAD).

Uses the app master_key to derive an encryption key via HKDF-SHA256.
Encrypted values are Fernet tokens (opaque URL-safe base64 strings).

Protects against DB file theft — an attacker without the master_key
cannot read encrypted fields. See security.md for full threat model.

Never log plaintext credentials or encrypted tokens.
"""

import base64
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

__all__ = [
    "DecryptionError",
    "decrypt_dict",
    "encrypt_dict",
]


class DecryptionError(Exception):
    """Raised when decryption fails (wrong key, corrupted token, tampered data)."""


def _derive_key(master_key: str) -> bytes:
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"wdiag:field-encryption:v1",
        info=b"",
    )
    return base64.urlsafe_b64encode(kdf.derive(master_key.encode()))


def encrypt_dict(data: dict[str, Any], master_key: str) -> str:
    """Serialize dict to JSON, encrypt, return Fernet token string."""
    fernet = Fernet(_derive_key(master_key))
    plaintext = json.dumps(data, separators=(",", ":")).encode()
    return fernet.encrypt(plaintext).decode()


def decrypt_dict(token: str, master_key: str) -> dict[str, Any]:
    """Decrypt a Fernet token and deserialize to dict.

    Raises DecryptionError on wrong key, corrupted token, or tampered data.
    """
    fernet = Fernet(_derive_key(master_key))
    try:
        plaintext = fernet.decrypt(token.encode())
    except InvalidToken as exc:
        raise DecryptionError("credential decryption failed") from exc
    result: dict[str, Any] = json.loads(plaintext.decode())
    return result
