"""TOTP (Time-based One-Time Password) support via pyotp.

Used as the second factor in local authentication and step-up auth.
"""

import pyotp  # type: ignore[import-untyped]


def generate_secret() -> str:
    """Generate a cryptographically random Base32 TOTP secret."""
    secret: str = pyotp.random_base32()
    return secret


def verify_code(secret: str, code: str, *, valid_window: int = 1) -> bool:
    """Verify a TOTP code against a secret.

    valid_window=1 allows one step (30 s) of clock drift in either direction.
    """
    result: bool = pyotp.TOTP(secret).verify(code, valid_window=valid_window)
    return result


def provisioning_uri(secret: str, email: str, issuer: str = "WDIAG") -> str:
    """Return the otpauth:// URI suitable for QR-code enrollment."""
    uri: str = pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)
    return uri
