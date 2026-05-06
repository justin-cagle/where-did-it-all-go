"""Security module.

Owns: JWT issuance/validation, password hashing, TOTP, auth plugin system,
rate limiting, and httpOnly cookie management.

Uses established, audited libraries only (see security.md):
  joserfc     — JWT (HS256)
  passlib     — argon2 password hashing
  pyotp       — TOTP
  pluggy      — auth plugin hook specs
  slowapi     — rate limiting

Import from sub-modules directly; this __init__.py only re-exports the
most-used public symbols.
"""

from app.security.encryption import DecryptionError, decrypt_dict, encrypt_dict
from app.security.jwt import (
    InvalidTokenError,
    has_step_up,
    issue_access_token,
    issue_step_up_token,
    validate_access_token,
)
from app.security.password import hash_password, needs_rehash, verify_password

__all__ = [
    "DecryptionError",
    "InvalidTokenError",
    "decrypt_dict",
    "encrypt_dict",
    "has_step_up",
    "hash_password",
    "issue_access_token",
    "issue_step_up_token",
    "needs_rehash",
    "validate_access_token",
    "verify_password",
]
